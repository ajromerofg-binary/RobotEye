"""
Transform de DNS inverso (PTR): dada una IP, resuelve el hostname asociado.

El complemento natural de `Domain → IPs`, que hasta ahora no tenía vuelta.
Consulta DNS pura y pública -- exactamente igual de pasivo que el resto de
transforms DNS del proyecto (MX, NS, etc.), sin tocar el objetivo.
"""
from typing import List, Tuple
import dns.resolver
import dns.reversename
import dns.exception

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class IPToPTR(Transform):
    name = "IP → PTR (DNS inverso)"
    description = "Resuelve el hostname asociado a la IP vía DNS inverso"
    input_types = ["IP"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        try:
            rev_name = dns.reversename.from_address(entity.value)
        except (dns.exception.SyntaxError, ValueError):
            raise RuntimeError(f"'{entity.value}' no es una dirección IP válida.")

        try:
            answers = dns.resolver.resolve(rev_name, "PTR", lifetime=10)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return []  # sin PTR configurado para esta IP, no es un error
        except dns.exception.DNSException as ex:
            raise RuntimeError(f"No se pudo resolver el PTR de '{entity.value}': {ex}")

        results = []
        for r in answers:
            hostname = r.to_text().rstrip(".")
            results.append((Entity(type="Domain", value=hostname), "PTR (DNS inverso)"))
        return results
