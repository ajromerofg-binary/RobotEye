"""
Analiza un correo sospechoso (fichero .eml, formato RFC 5322 estándar que
exportan Outlook, Gmail, Thunderbird...) y extrae remitente, destinatarios,
IP de origen real, resultado de SPF/DKIM/DMARC, enlaces del cuerpo y
hashes de adjuntos -- pensado para el triaje inicial de un correo de
spearphishing que ya has recibido tú o te ha remitido un cliente.

Usa únicamente el módulo `email` de la librería estándar de Python -- sin
dependencias nuevas, sin conectar a ningún servidor de correo. Es
análisis forense de un fichero que ya tienes, no acceso a ningún buzón.

Aviso honesto sobre fiabilidad: las cabeceras `Received` las puede
falsificar quien controla el punto de origen -- solo las que añaden TUS
propios servidores de correo (las más recientes, al principio del
fichero) son fiables al 100%. La IP de origen que extrae esta función es
la del primer salto registrado, que en la mayoría de phishing real sí es
la infraestructura del atacante (rara vez se molestan en falsificar toda
la cadena), pero no es una certeza matemática -- una pista fuerte, no una
prueba.
"""
import re
from email import message_from_binary_file
from email.utils import parseaddr, getaddresses
from email.message import Message
from typing import Dict, Any, List, Optional
import hashlib

_URL_PATTERN = re.compile(r'https?://[^\s<>"\')\]]+')
_IPV4_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')


def _extract_origin_ip(received_headers: List[str]) -> Optional[str]:
    """La cabecera Received más ANTIGUA (última de la lista, ya que cada
    servidor añade la suya al principio) es la más cercana al origen real."""
    if not received_headers:
        return None
    oldest = received_headers[-1]
    match = _IPV4_PATTERN.search(oldest)
    return match.group(0) if match else None


def _parse_auth_results(header_value: Optional[str]) -> Dict[str, Optional[str]]:
    """Extrae spf=/dkim=/dmarc= del texto libre de Authentication-Results.
    El formato no está 100% estandarizado entre proveedores de correo, así
    que se busca el patrón 'campo=valor' en vez de asumir una estructura
    fija -- si un proveedor no incluye alguno, se informa como no
    disponible en vez de inventar un resultado."""
    result = {"spf": None, "dkim": None, "dmarc": None}
    if not header_value:
        return result
    for campo in result:
        match = re.search(rf"{campo}=(\w+)", header_value, re.IGNORECASE)
        if match:
            result[campo] = match.group(1).lower()
    return result


def _extract_body_text(msg: Message) -> str:
    if msg.is_multipart():
        partes = []
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    partes.append(part.get_payload(decode=True).decode(errors="replace"))
                except Exception:
                    continue
        return "\n".join(partes)
    try:
        return msg.get_payload(decode=True).decode(errors="replace")
    except Exception:
        return str(msg.get_payload())


def _extract_attachments(msg: Message) -> List[Dict[str, Any]]:
    attachments = []
    if not msg.is_multipart():
        return attachments
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue
        filename = part.get_filename() or "(sin nombre)"
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        attachments.append({
            "filename": filename,
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "md5": hashlib.md5(payload).hexdigest(),
        })
    return attachments


def analyze_eml(path: str) -> Dict[str, Any]:
    with open(path, "rb") as f:
        msg = message_from_binary_file(f)

    from_name, from_address = parseaddr(msg.get("From", ""))
    reply_to_name, reply_to_address = parseaddr(msg.get("Reply-To", ""))
    return_path_name, return_path_address = parseaddr(msg.get("Return-Path", ""))

    to_addresses = [addr for _, addr in getaddresses(msg.get_all("To", [])) if addr]
    cc_addresses = [addr for _, addr in getaddresses(msg.get_all("Cc", [])) if addr]

    auth_results = _parse_auth_results(msg.get("Authentication-Results"))
    origin_ip = _extract_origin_ip(msg.get_all("Received", []))
    body_text = _extract_body_text(msg)
    urls = sorted(set(_URL_PATTERN.findall(body_text)))
    attachments = _extract_attachments(msg)

    from_domain = from_address.rsplit("@", 1)[-1].lower() if "@" in from_address else None
    reply_to_domain = reply_to_address.rsplit("@", 1)[-1].lower() if "@" in reply_to_address else None

    indicadores = []
    if reply_to_address and reply_to_domain and from_domain and reply_to_domain != from_domain:
        indicadores.append(
            f"Reply-To ({reply_to_address}) apunta a un dominio distinto del remitente ({from_domain})"
        )
    if return_path_address and from_domain and return_path_address.rsplit("@", 1)[-1].lower() != from_domain:
        indicadores.append(
            f"Return-Path ({return_path_address}) no coincide con el dominio del remitente ({from_domain})"
        )
    if auth_results["spf"] == "fail":
        indicadores.append("SPF ha fallado: el servidor emisor no está autorizado por el dominio del remitente")
    if auth_results["dmarc"] == "fail":
        indicadores.append("DMARC ha fallado: el correo no supera la política de autenticación del dominio")
    # NOTA: se probó también un indicador de "el nombre mostrado no
    # coincide con el dominio" (para detectar suplantación de marca, ej.
    # "Microsoft" desde un dominio ajeno) -- descartado tras comprobar con
    # un caso de prueba real que genera muchísimos falsos positivos: el
    # patrón normal y mayoritario es que el nombre de una PERSONA (ej.
    # "Ana Lopez") no tenga ninguna relación léxica con el dominio de su
    # propia empresa, y eso no es sospechoso en absoluto. Distinguir de
    # forma fiable "nombre de marca suplantada" de "nombre de persona
    # normal" no es viable con una heurística simple sin arriesgar avisar
    # de spoofing en la mayoría de correos legítimos -- se deja el nombre
    # y el dominio como propiedades visibles para que el usuario lo
    # valore él mismo, en vez de una alerta automática poco fiable.

    return {
        "from_name": from_name,
        "from_address": from_address,
        "from_domain": from_domain,
        "to_addresses": to_addresses,
        "cc_addresses": cc_addresses,
        "reply_to_address": reply_to_address or None,
        "return_path_address": return_path_address or None,
        "subject": msg.get("Subject", "(sin asunto)"),
        "date": msg.get("Date", "desconocida"),
        "message_id": msg.get("Message-ID", "desconocido"),
        "spf": auth_results["spf"],
        "dkim": auth_results["dkim"],
        "dmarc": auth_results["dmarc"],
        "origin_ip": origin_ip,
        "urls_in_body": urls,
        "attachments": attachments,
        "spoofing_indicators": indicadores,
    }


def populate_graph_from_analysis(model, scene, analysis: Dict[str, Any]):
    """Puebla el grafo con el resultado de analyze_eml(), reutilizando los
    tipos de entidad que ya existen (Email, IP, Domain, URL, Hash) --
    ninguno de ellos es nuevo, así que las 60 transforms que ya tiene la
    app aplican de inmediato a lo que aparezca aquí (WHOIS del dominio,
    RDAP de la IP, verificar el buzón del remitente...).

    Devuelve la entidad `EmailMessage` central, a la que quedan
    conectadas todas las demás."""
    from core.entity_types import Entity

    resumen_props = {
        "asunto": analysis["subject"],
        "fecha": analysis["date"],
        "message_id": analysis["message_id"],
        "remitente_nombre": analysis["from_name"] or "(sin nombre mostrado)",
        "spf": analysis["spf"] or "no disponible en las cabeceras",
        "dkim": analysis["dkim"] or "no disponible en las cabeceras",
        "dmarc": analysis["dmarc"] or "no disponible en las cabeceras",
    }
    if analysis["spoofing_indicators"]:
        resumen_props["indicadores_de_suplantacion"] = " | ".join(analysis["spoofing_indicators"])
    else:
        resumen_props["indicadores_de_suplantacion"] = "ninguno detectado automáticamente (revisar igualmente a mano)"

    email_msg_entity = Entity(type="EmailMessage", value=analysis["subject"] or "(sin asunto)", properties=resumen_props)
    model.add_entity(email_msg_entity)
    scene.add_entity_visual(email_msg_entity)

    def _link(entity_type, value, label, extra_props=None):
        entity_id = model.add_entity(Entity(type=entity_type, value=value, properties=extra_props or {}))
        real_entity = model.get_entity(entity_id)
        scene.add_entity_visual(real_entity)
        model.add_relation(email_msg_entity.id, entity_id, label)
        scene.add_relation_visual(email_msg_entity, real_entity, label)
        return real_entity

    if analysis["from_address"]:
        _link("Email", analysis["from_address"], "remitente")
    if analysis["from_domain"]:
        _link("Domain", analysis["from_domain"], "dominio del remitente")
    for addr in analysis["to_addresses"]:
        _link("Email", addr, "destinatario (Para)")
    for addr in analysis["cc_addresses"]:
        _link("Email", addr, "destinatario (Cc)")
    if analysis["reply_to_address"]:
        _link("Email", analysis["reply_to_address"], "Reply-To")
    if analysis["origin_ip"]:
        _link("IP", analysis["origin_ip"], "IP de origen (cabecera Received más antigua)")
    for url in analysis["urls_in_body"]:
        _link("URL", url, "enlace en el cuerpo del correo")
    for adj in analysis["attachments"]:
        _link("Hash", adj["sha256"], "adjunto (SHA-256)", extra_props={
            "nombre_fichero": adj["filename"],
            "tamano_bytes": adj["size_bytes"],
            "md5": adj["md5"],
        })

    return email_msg_entity
