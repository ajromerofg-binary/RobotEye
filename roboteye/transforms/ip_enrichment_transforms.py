"""
Dos transforms nuevas para `IP`, cerrando huecos reales encontrados en la
auditoría de cobertura de esta ronda:

- `IP → RDAP`: el equivalente de `Domain → WHOIS info` pero para IPs.
  RDAP (Registration Data Access Protocol, RFC 9083) es el reemplazo
  moderno y estandarizado de WHOIS -- responde en JSON en vez de texto
  libre. rdap.org actúa de "bootstrap": redirige automáticamente (HTTP
  302) al RIR correcto (ARIN/RIPE/APNIC/LACNIC/AFRINIC) según a quién
  pertenezca la IP, sin que haga falta saber de antemano cuál consultar.

- `IP → Comprobar en listas negras (DNSBL)`: consulta Spamhaus ZEN, la
  lista negra de IPs más usada del mundo para filtrado de spam. Es
  puramente DNS (una resolución A contra un nombre especial), gratis,
  pública, sin necesidad de key -- pero sujeta a "fair use" de Spamhaus
  (uso no comercial, volumen razonable): no pensada para consultar miles
  de IPs seguidas, sí perfectamente para consultas puntuales de OSINT.
"""
from typing import List, Tuple, Optional
import requests
import dns.resolver
import dns.exception

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import BROWSER_HEADERS
from transforms.asn_transforms import _reverse_ipv4


def _extract_entity_name(entities: Optional[list]) -> str:
    """Los datos de contacto en RDAP vienen en formato vCard (RFC 6350)
    dentro de cada entidad -- buscamos la propiedad 'fn' (nombre formateado),
    que es el nombre legible de la organización o persona de contacto."""
    for ent in entities or []:
        vcard = ent.get("vcardArray")
        if not vcard or len(vcard) < 2:
            continue
        for prop in vcard[1]:
            if len(prop) >= 4 and prop[0] == "fn" and prop[3]:
                return str(prop[3])
    return ""


@register
class IPToRDAP(Transform):
    name = "IP → RDAP (registro del bloque de red)"
    description = "Quién tiene asignado el bloque de red al que pertenece la IP -- reemplazo moderno de WHOIS (RFC 9083)"
    input_types = ["IP"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            f"https://rdap.org/ip/{entity.value}",
            headers={**BROWSER_HEADERS, "Accept": "application/rdap+json"},
            timeout=15,
        )
        if resp.status_code == 404:
            raise RuntimeError(
                f"rdap.org no conoce ningún servidor RDAP autoritativo para "
                f"'{entity.value}' (solo indexa servidores registrados en IANA)."
            )
        resp.raise_for_status()
        data = resp.json()

        entity.properties.update({
            "rdap_nombre_red": data.get("name") or "desconocido",
            "rdap_pais": data.get("country") or "desconocido",
            "rdap_rango": f"{data.get('startAddress', '?')} - {data.get('endAddress', '?')}",
            "rdap_tipo_asignacion": data.get("type") or "desconocido",
        })

        organizacion = _extract_entity_name(data.get("entities"))
        if organizacion:
            return [(Entity(type="Organization", value=organizacion), "organización del bloque de red (RDAP)")]
        return []


# Códigos de retorno de Spamhaus ZEN (ver spamhaus.org/faqs/dnsbl-usage) --
# 127.255.255.* NO es un listado real, es una señal de error (resolutor
# abierto, volumen excesivo, zona mal escrita); hay que distinguirlo de un
# listado de verdad para no dar un falso positivo.
ZEN_CODES = {
    "127.0.0.2": "SBL (spammer conocido, listado manual de Spamhaus)",
    "127.0.0.3": "CSS (spam de bajo volumen / snowshoe)",
    "127.0.0.4": "XBL (equipo comprometido: malware, proxy abierto, botnet)",
    "127.0.0.9": "SBL DROP (bloque de red secuestrado o robado)",
    "127.0.0.10": "PBL (rango residencial/dinámico, no debería enviar correo directo -- gestionado por el ISP)",
    "127.0.0.11": "PBL (rango residencial/dinámico -- gestionado por Spamhaus)",
}


@register
class IPToBlocklist(Transform):
    name = "IP → Comprobar en listas negras (DNSBL)"
    description = "Consulta Spamhaus ZEN (DNS puro, gratis) para ver si la IP está en alguna lista negra de spam/abuso"
    input_types = ["IP"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        query_name = f"{_reverse_ipv4(entity.value)}.zen.spamhaus.org"
        try:
            answers = dns.resolver.resolve(query_name, "A", lifetime=8)
        except dns.resolver.NXDOMAIN:
            entity.properties["listas_negras"] = "no listada en Spamhaus ZEN"
            return []
        except dns.exception.DNSException as ex:
            raise RuntimeError(f"No se pudo consultar Spamhaus ZEN: {ex}")

        codigos = [str(r) for r in answers]
        # El rango 127.255.255.* son errores de la propia consulta (no un
        # listado real) -- normalmente por volumen excesivo o resolutor
        # abierto. Se informa como tal, nunca como "está en una lista negra".
        if all(c.startswith("127.255.255.") for c in codigos):
            raise RuntimeError(
                "Spamhaus devolvió un código de error de consulta (127.255.255.*), "
                "no un listado real -- suele deberse a exceso de consultas o a usar "
                "un resolutor DNS público/abierto. No se puede determinar el estado "
                "de esta IP por ahora."
            )

        listados = [ZEN_CODES.get(c, f"código no documentado ({c})") for c in codigos]
        entity.properties["listas_negras"] = "; ".join(listados)
        return []
