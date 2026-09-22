"""
Definición de los tipos de entidad soportados por el grafo.
Cada entidad tiene un tipo, un valor (label principal) y propiedades extra.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import ipaddress
import re
import uuid


ENTITY_ICONS = {
    "Domain": "🌐",
    "IP": "🖥️",
    "Email": "✉️",
    "Person": "👤",
    "ASN": "🛰️",
    "Phone": "📞",
    "URL": "🔗",
    "Organization": "🏢",
    "Hash": "#️⃣",
    "Dork": "🎯",
    "Breach": "🔓",
    "Username": "🆔",
    "Paste": "📋",
    "Software": "🧩",
    "MACAddress": "📡",
    "EmailMessage": "📨",
}


@dataclass
class Entity:
    """Representa un nodo del grafo (una entidad tipo Maltego)."""
    type: str                      # "Domain", "IP", "Email", ...
    value: str                     # el valor principal (ej: "example.com")
    properties: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_note: str = ""            # nota manual del usuario -- nunca la escribe
                                    # ninguna transform, campo aparte a propósito
                                    # para que no pueda chocar con nada de 'properties'

    @property
    def icon(self) -> str:
        return ENTITY_ICONS.get(self.type, "❔")

    @property
    def label(self) -> str:
        return self.value

    def __repr__(self):
        return f"<Entity {self.type}:{self.value}>"


VALID_TYPES = list(ENTITY_ICONS.keys())

_DOMAIN_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$"
)


def guess_entity_type(value: str) -> Optional[str]:
    """Heurística CONSERVADORA para autodetectar el tipo de una entidad a
    partir de su valor, usada por la importación masiva. Solo devuelve un
    tipo cuando el patrón es inequívoco (Email, URL, IP) o razonablemente
    fiable (Domain, con TLD no numérico para no confundir cosas como
    "3.14" con un dominio) -- si no está segura, devuelve None para que
    quien la use recurra al tipo seleccionado por defecto en vez de
    arriesgar una clasificación incorrecta y silenciosa."""
    value = value.strip()
    if not value or " " in value:
        return None

    if value.count("@") == 1:
        local, _, domain_part = value.partition("@")
        if local and "." in domain_part:
            return "Email"

    if value.lower().startswith(("http://", "https://")):
        return "URL"

    try:
        ipaddress.ip_address(value)
        return "IP"
    except ValueError:
        pass

    if _DOMAIN_PATTERN.match(value):
        tld = value.rsplit(".", 1)[-1]
        if not tld.isdigit():
            return "Domain"

    return None
