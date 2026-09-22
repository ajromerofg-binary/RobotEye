"""
Transform de postura de seguridad de email de un dominio: SPF, DKIM y DMARC.

Los tres son registros TXT de DNS públicos -- OSINT puramente pasivo, la
misma naturaleza que las transforms de DNS que ya existen en el proyecto.
Útil en auditoría GRC/postura de seguridad: un dominio sin SPF/DMARC (o con
una política DMARC laxa) es mucho más fácil de suplantar por phishing.

  - SPF: registro TXT en el propio dominio, empieza por "v=spf1".
  - DMARC: registro TXT en "_dmarc.<dominio>", empieza por "v=DMARC1".
  - DKIM: a diferencia de SPF/DMARC, no vive en una ubicación fija -- el
    "selector" (el subdominio antes de "._domainkey.") lo elige quien
    configuró el DNS, y no hay forma de listarlos todos sin acceso interno.
    Por eso se prueba una lista de selectores habituales (los que usan por
    defecto Google Workspace, Microsoft 365, Mailchimp y otros proveedores
    grandes) -- si ninguno responde, no significa necesariamente que no
    haya DKIM configurado, solo que no usa ninguno de los selectores
    comunes que probamos.
"""
from typing import List, Tuple, Optional
import dns.resolver
import dns.exception

from core.entity_types import Entity
from core.transform_base import Transform, register


# Selectores DKIM más habituales en uso real, por proveedor de correo.
COMMON_DKIM_SELECTORS = [
    "google",       # Google Workspace
    "selector1", "selector2",  # Microsoft 365
    "default",      # muchos proveedores genéricos / cPanel
    "k1",           # Mailchimp / Mandrill
    "dkim",
    "mail",
    "smtp",
    "s1", "s2",
]


def _query_txt_records(name: str) -> List[str]:
    try:
        answers = dns.resolver.resolve(name, "TXT", lifetime=15)
    except dns.exception.DNSException:
        # Cubre NXDOMAIN, NoAnswer, timeouts y cualquier otro fallo de resolución:
        # en todos los casos, simplemente no pudimos obtener el registro. Dominios
        # grandes (Google, GitHub...) suelen tener docenas de TXT de verificación
        # de terceros, lo que puede forzar respuestas grandes vía TCP y tardar más
        # que un dominio pequeño -- por eso el timeout es generoso (15s).
        return []
    records = []
    for r in answers:
        # Un TXT puede venir partido en varios "strings" concatenados (límite
        # de 255 bytes por string); r.strings los da por separado, hay que unirlos.
        if hasattr(r, "strings"):
            text = "".join(s.decode() if isinstance(s, bytes) else s for s in r.strings)
        else:
            text = r.to_text().strip('"')
        records.append(text)
    return records


@register
class DomainToEmailSecurity(Transform):
    name = "Domain → SPF / DKIM / DMARC"
    description = "Lee la postura de seguridad de email del dominio (registros TXT públicos)"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        domain = entity.value

        spf = self._find_spf(domain)
        dmarc = self._find_dmarc(domain)
        dkim_selectors = self._probe_dkim_selectors(domain)

        entity.properties.update({
            "spf": spf or "no publicado",
            "dmarc": dmarc or "no publicado",
            "dkim_selectores_detectados": ", ".join(dkim_selectors) if dkim_selectors
                else "ninguno de los selectores habituales probados (puede que use uno distinto)",
        })
        return []  # transform de enriquecimiento puro: no genera nodos nuevos, solo detalles

    @staticmethod
    def _find_spf(domain: str) -> Optional[str]:
        for record in _query_txt_records(domain):
            if record.lower().startswith("v=spf1"):
                return record
        return None

    @staticmethod
    def _find_dmarc(domain: str) -> Optional[str]:
        for record in _query_txt_records(f"_dmarc.{domain}"):
            if record.lower().startswith("v=dmarc1"):
                return record
        return None

    @staticmethod
    def _probe_dkim_selectors(domain: str) -> List[str]:
        found = []
        for selector in COMMON_DKIM_SELECTORS:
            records = _query_txt_records(f"{selector}._domainkey.{domain}")
            if records:
                found.append(selector)
        return found
