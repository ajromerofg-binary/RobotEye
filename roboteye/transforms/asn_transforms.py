"""
Transform de resolución de ASN (Autonomous System Number) para una IP.

Usa el servicio de "whois vía DNS" de Team Cymru (https://team-cymru.com/ip-asn-mapping/),
público y gratuito desde hace más de 15 años, sin API key. En vez de un
protocolo whois propio, expone los datos como registros TXT de DNS -- una
técnica ingeniosa que aprovecha la infraestructura DNS ya existente y es
extremadamente rápida y fiable.

Funcionamiento (OSINT puramente pasivo, solo se consulta un tercero, nunca
se toca el objetivo): se invierten los octetos de la IP y se hace una
consulta TXT a "<ip-invertida>.origin.asn.cymru.com", que devuelve el ASN,
el prefijo BGP, el país y el registro regional (RIPE/ARIN/APNIC...). Una
segunda consulta a "AS<n>.asn.cymru.com" da el nombre de la organización
dueña de ese ASN.
"""
import re
from typing import List, Tuple, Optional
import dns.resolver
import dns.exception
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register


def _reverse_ipv4(ip: str) -> str:
    octets = ip.split(".")
    return ".".join(reversed(octets))


def _extract_asn_number(value: str) -> str:
    """Extrae solo los dígitos del número de ASN a partir del valor de la
    entidad (ej. 'AS15169' -> '15169'). Usar .lstrip('AS') aquí sería un bug
    clásico de Python: lstrip trata su argumento como un CONJUNTO de
    caracteres a quitar, no como un prefijo literal -- 'ASN13335'.lstrip('AS')
    da 'N13335' (mal), no '13335'. Extraer los dígitos es robusto de verdad
    frente a cómo haya escrito el usuario el valor (con o sin 'AS', con o
    sin espacios)."""
    digits = re.sub(r"\D", "", value)
    if not digits:
        raise RuntimeError(f"'{value}' no contiene ningún número de ASN reconocible.")
    return digits


def _query_txt(name: str) -> Optional[str]:
    try:
        answers = dns.resolver.resolve(name, "TXT", lifetime=10)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return None
    record = answers[0].to_text().strip('"')
    return record


@register
class IPToASN(Transform):
    name = "IP → ASN (Team Cymru)"
    description = "Consulta el ASN, prefijo BGP y organización de la IP vía DNS público (sin API key)"
    input_types = ["IP"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        ip = entity.value
        if ":" in ip:
            raise RuntimeError(
                "Esta consulta a Team Cymru solo soporta IPv4 en este proyecto. "
                f"'{ip}' parece IPv6."
            )

        try:
            origin_txt = _query_txt(f"{_reverse_ipv4(ip)}.origin.asn.cymru.com")
        except dns.exception.DNSException as ex:
            raise RuntimeError(f"No se pudo consultar Team Cymru: {ex}")

        if not origin_txt:
            return []  # IP no anunciada en BGP público (rango privado, no asignado, etc.)

        # Formato: "ASN | Prefijo BGP | País | Registro regional | Fecha de asignación"
        parts = [p.strip() for p in origin_txt.split("|")]
        if len(parts) < 4:
            return []
        asn_number, prefix, country, registry = parts[0], parts[1], parts[2], parts[3]

        # Puede haber varios ASN anunciando el mismo rango (multihoming);
        # nos quedamos con el primero, que es el caso normal.
        asn_number = asn_number.split()[0]

        org_name = None
        try:
            name_txt = _query_txt(f"AS{asn_number}.asn.cymru.com")
        except dns.exception.DNSException:
            name_txt = None
        if name_txt:
            # Formato: "ASN | País | Registro regional | Fecha | Nombre de la organización"
            name_parts = [p.strip() for p in name_txt.split("|")]
            if len(name_parts) >= 5:
                org_name = name_parts[4]

        asn_entity = Entity(type="ASN", value=f"AS{asn_number}", properties={
            "prefijo_bgp": prefix,
            "pais": country,
            "registro_regional": registry,
            "organizacion": org_name or "desconocida",
        })
        return [(asn_entity, "IP anunciada por este ASN")]


@register
class ASNToOrganization(Transform):
    name = "ASN → Organización (Team Cymru)"
    description = "Extrae la organización dueña del ASN como nodo propio, para pivotar (Organization → Domain, dorks...)"
    input_types = ["ASN"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        asn_number = _extract_asn_number(entity.value)
        try:
            name_txt = _query_txt(f"AS{asn_number}.asn.cymru.com")
        except dns.exception.DNSException as ex:
            raise RuntimeError(f"No se pudo consultar Team Cymru: {ex}")

        if not name_txt:
            return []

        # Formato: "ASN | País | Registro regional | Fecha | Nombre de la organización"
        parts = [p.strip() for p in name_txt.split("|")]
        if len(parts) < 5 or not parts[4]:
            return []

        org_entity = Entity(type="Organization", value=parts[4], properties={
            "pais": parts[1] if len(parts) > 1 else "desconocido",
            "registro_regional": parts[2] if len(parts) > 2 else "desconocido",
        })
        return [(org_entity, "organización dueña del ASN")]


@register
class ASNToPrefixes(Transform):
    name = "ASN → Prefijos de red (RIPEstat)"
    description = "Lista los rangos IP (CIDR) que este ASN anuncia en BGP (RIPEstat, gratis, sin key)"
    input_types = ["ASN"]

    API_URL = "https://stat.ripe.net/data/announced-prefixes/data.json"

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        asn_number = _extract_asn_number(entity.value)
        resp = requests.get(
            self.API_URL,
            params={"resource": asn_number},
            headers={"User-Agent": "RobotEye-OSINT-Tool"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        # .get() en vez de acceso directo ["prefix"]: si algún elemento de
        # la respuesta real de RIPEstat viene incompleto (sin la clave
        # "prefix", ej. solo con "timelines"), un acceso directo por clave
        # crashearía la transform entera por un único dato incompleto en
        # vez de aprovechar el resto -- bug real encontrado en la auditoría
        # de esta ronda.
        # .get(key) or {} / or [] en cadena -- no .get(key, {}) -- si la
        # API devuelve "data": null explícito (no solo ausente), el default
        # posicional de .get() no se aplicaría (la clave SÍ existe, solo que
        # con valor null) y el .get() encadenado sobre None crashearía.
        prefixes = [p["prefix"] for p in (data.get("data") or {}).get("prefixes", []) or [] if "prefix" in p]
        if not prefixes:
            return []

        entity.properties["prefijos_anunciados"] = ", ".join(prefixes[:30])
        entity.properties["total_prefijos"] = len(prefixes)
        return []  # enriquecimiento puro: no generamos nodos IP a partir de rangos CIDR (tipos distintos)
