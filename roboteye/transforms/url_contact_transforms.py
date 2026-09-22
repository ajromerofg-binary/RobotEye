"""
Transform de extracción de contacto (emails + teléfonos) de una URL cualquiera.

Equivalente a las transforms "Found on this web page" de Maltego, pero
genérico: aplica a CUALQUIER nodo URL que ya tengas en el grafo (un perfil
de GitHub, un snapshot de Wayback, un resultado de un dork, un enlace de un
paste...), no solo a las páginas que auto-descubre el harvesting de
Domain. A diferencia de `Domain → Emails` / `Domain → Teléfonos`, aquí no
se filtra por dominio: se extrae cualquier email o teléfono visible en el
contenido de esa página concreta, tal cual aparezca.
"""
import re
from typing import List, Tuple
import phonenumbers
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import BROWSER_HEADERS as COMMON_HEADERS
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Extensiones que claramente no son HTML/texto -- las descartamos antes de
# perder tiempo parseando binarios en busca de patrones de texto.
NON_TEXT_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".mp4", ".mp3", ".wav", ".zip", ".exe", ".dmg",
)


@register
class URLToContactInfo(Transform):
    name = "URL → Emails y teléfonos (contenido de la página)"
    description = "Descarga la página y extrae cualquier email o teléfono visible en su contenido"
    input_types = ["URL"]

    FETCH_TIMEOUT = 15

    def applies_to(self, entity: Entity) -> bool:
        if entity.type != "URL":
            return False
        lower = entity.value.lower().split("?")[0].split("#")[0]
        return not lower.endswith(NON_TEXT_EXTENSIONS)

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(entity.value, headers=COMMON_HEADERS, timeout=self.FETCH_TIMEOUT)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if content_type and not any(t in content_type for t in ("text", "html", "json", "xml")):
            return []  # binario inesperado pese a la extensión (ej. redirect a un PDF), no es un error

        text = resp.text

        emails = {m.group(0).lower() for m in EMAIL_RE.finditer(text)}
        phones = set()
        try:
            for match in phonenumbers.PhoneNumberMatcher(text, None):
                phones.add(phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164))
        except Exception:
            pass

        results = []
        for email in sorted(emails):
            email_entity = Entity(type="Email", value=email, properties={
                "origen": f"encontrado en el contenido de {entity.value}",
            })
            results.append((email_entity, "email en la página"))
        for phone in sorted(phones):
            phone_entity = Entity(type="Phone", value=phone, properties={
                "origen": f"encontrado en el contenido de {entity.value}",
            })
            results.append((phone_entity, "teléfono en la página"))
        return results
