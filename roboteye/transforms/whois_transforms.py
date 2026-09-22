"""
Transform WHOIS: Domain -> Organization / Person / Email / Phone (registrante).
Usa python-whois, consulta directa al protocolo whois, sin API key.
"""
from typing import List, Tuple
import whois as pywhois

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class DomainToWhois(Transform):
    name = "Domain → WHOIS info"
    description = "Consulta WHOIS y extrae organización, email, teléfono y nombre del registrante"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        results = []
        w = pywhois.whois(entity.value)

        org = getattr(w, "org", None)
        if org:
            if isinstance(org, list):
                org = org[0]
            org = str(org).strip()
        if org:
            results.append((Entity(type="Organization", value=org), "registrante (org)"))

        name = getattr(w, "name", None)
        if name:
            if isinstance(name, list):
                name = name[0]
            name = str(name).strip()
        if name:
            results.append((Entity(type="Person", value=name), "registrante (nombre)"))

        emails = getattr(w, "emails", None) or []
        if isinstance(emails, str):
            emails = [emails]
        for email in emails:
            email = str(email).strip()
            if email:
                results.append((Entity(type="Email", value=email), "email WHOIS"))

        # El nombre del campo de teléfono varía según qué parser de TLD haya
        # coincidido (no todos los registros WHOIS usan las mismas etiquetas) --
        # probamos los más habituales en orden de fiabilidad.
        phone = None
        for field in ("registrant_phone", "phone", "admin_phone", "registrant_phone_number"):
            value = getattr(w, field, None)
            if value:
                phone = value[0] if isinstance(value, list) else value
                break
        if phone:
            results.append((Entity(type="Phone", value=str(phone).strip()), "teléfono WHOIS"))

        # Guardamos el resto de datos crudos como propiedades del propio dominio.
        # or "desconocido"/fecha formateada: sin esto, un campo ausente
        # guardaría el literal None (o la cadena "None" tras el str()) --
        # el mismo bug de calidad de datos que ya se encontró y corrigió en
        # IPToGeolocation durante la auditoría de esta ronda.
        registrar = getattr(w, "registrar", None)
        entity.properties["whois_registrar"] = registrar if registrar else "desconocido"
        creation = getattr(w, "creation_date", None)
        entity.properties["whois_creation_date"] = str(creation) if creation else "desconocida"
        expiration = getattr(w, "expiration_date", None)
        entity.properties["whois_expiration_date"] = str(expiration) if expiration else "desconocida"

        return results
