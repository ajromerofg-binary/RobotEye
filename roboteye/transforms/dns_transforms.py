"""
Transforms DNS: Domain -> IP(s), Domain -> MX, Domain -> NS.
Usa dnspython, sin API keys.
"""
from typing import List, Tuple
import dns.resolver

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class DomainToIPs(Transform):
    name = "Domain → IPs (A/AAAA)"
    description = "Resuelve registros A/AAAA del dominio"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        results = []
        for rtype in ("A", "AAAA"):
            try:
                answers = dns.resolver.resolve(entity.value, rtype, lifetime=5)
                for rdata in answers:
                    ip = rdata.to_text()
                    results.append((Entity(type="IP", value=ip), f"resuelve a ({rtype})"))
            except Exception:
                continue
        return results


@register
class DomainToMX(Transform):
    name = "Domain → MX"
    description = "Obtiene servidores de correo del dominio"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        results = []
        try:
            answers = dns.resolver.resolve(entity.value, "MX", lifetime=5)
            for rdata in answers:
                host = str(rdata.exchange).rstrip(".")
                results.append((Entity(type="Domain", value=host), "MX"))
        except Exception:
            pass
        return results


@register
class DomainToNS(Transform):
    name = "Domain → NS"
    description = "Obtiene servidores de nombres del dominio"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        results = []
        try:
            answers = dns.resolver.resolve(entity.value, "NS", lifetime=5)
            for rdata in answers:
                host = str(rdata.target).rstrip(".")
                results.append((Entity(type="Domain", value=host), "NS"))
        except Exception:
            pass
        return results


@register
class DomainToSOA(Transform):
    name = "Domain → SOA (email del administrador técnico)"
    description = "Lee el registro SOA del dominio -- suele contener el email del administrador técnico de la zona DNS"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        try:
            answers = dns.resolver.resolve(entity.value, "SOA", lifetime=5)
        except Exception:
            return []

        soa = answers[0]
        primary_ns = str(soa.mname).rstrip(".")

        # El campo 'rname' del SOA es el email del administrador, pero con un
        # formato heredado de los años 80: el primer "." SIN ESCAPAR hace de
        # "@" (por compatibilidad con formatos de correo pre-internet). Ej: el
        # valor DNS "hostmaster.ejemplo.com." representa "hostmaster@ejemplo.com".
        rname_raw = str(soa.rname).rstrip(".")
        admin_email = _soa_rname_to_email(rname_raw)

        entity.properties.update({
            "soa_servidor_primario": primary_ns,
            "soa_email_administrador": admin_email,
            "soa_serial": soa.serial,
        })

        results = [(Entity(type="Domain", value=primary_ns), "servidor primario (SOA)")]
        if "@" in admin_email:
            results.append((Entity(type="Email", value=admin_email), "email del administrador técnico (SOA)"))
        return results


def _soa_rname_to_email(rname_raw: str) -> str:
    """Convierte el campo rname de un registro SOA al formato email real.

    El primer punto SIN ESCAPAR actúa de separador "@"; un punto escapado
    (\\.) dentro de la parte local (poco común, pero válido si el buzón del
    administrador tiene un punto en su nombre, ej. "john.doe@ejemplo.com")
    se desescapa a un punto normal en vez de usarse como separador. Un
    reemplazo ingenuo del primer "." a secas (sin mirar el escape) rompería
    ese caso -- se detectó y corrigió durante el testing de esta transform.
    """
    i = 0
    while i < len(rname_raw):
        if rname_raw[i] == "." and (i == 0 or rname_raw[i - 1] != "\\"):
            break
        i += 1
    if i >= len(rname_raw):
        return rname_raw  # no se encontró separador sin escapar; devolver tal cual
    local_part = rname_raw[:i].replace("\\.", ".")
    domain_part = rname_raw[i + 1:]
    return f"{local_part}@{domain_part}"
