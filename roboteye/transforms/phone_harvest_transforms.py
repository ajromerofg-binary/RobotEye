"""
Transform de búsqueda de números de teléfono asociados a un dominio.

Mismo patrón que `Domain → Emails` (email_harvest_transforms.py): busca el
dominio en DuckDuckGo, y además visita las primeras páginas encontradas por
si el teléfono aparece en el cuerpo pero no en el snippet corto de
búsqueda. Mismo nivel de contacto pasivo que el resto de transforms
basadas en DuckDuckGo del proyecto.

A diferencia del email harvest (que usa una regex simple porque el patrón
"algo@dominio.com" es inequívoco), aquí usamos `phonenumbers.PhoneNumberMatcher`
-- ya es dependencia del proyecto (core/phone_transforms.py) y sabe
reconocer números de teléfono válidos en texto libre de muchas regiones
distintas, mucho más fiable que una regex hecha a mano.
"""
from typing import List, Tuple, Set
import phonenumbers
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import DorkToResults, BROWSER_HEADERS as COMMON_HEADERS, is_ddg_blocked, DDG_BLOCK_MESSAGE



def _extract_phones(text: str) -> Set[str]:
    found = set()
    try:
        for match in phonenumbers.PhoneNumberMatcher(text, None):
            found.add(phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164))
    except Exception:
        pass  # texto imposible de parsear (binario, encoding raro...); no es un error del dominio
    return found


@register
class DomainToPhoneHarvest(Transform):
    name = "Domain → Teléfonos (búsqueda web)"
    description = "Busca números de teléfono publicados del dominio en páginas ya indexadas (gratis, sin key)"
    input_types = ["Domain"]
    uses_ddg = True

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    MAX_PAGES_TO_FETCH = 5
    PAGE_FETCH_TIMEOUT = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        domain = entity.value
        resp = requests.get(
            self.SEARCH_URL,
            params={"q": f'"{domain}" "tel" OR "phone" OR "teléfono"'},
            headers=COMMON_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        if is_ddg_blocked(resp.text):
            raise RuntimeError(DDG_BLOCK_MESSAGE)

        found_phones: Set[str] = set()
        found_phones |= _extract_phones(resp.text)

        urls = DorkToResults.parse_results(resp.text, limit=self.MAX_PAGES_TO_FETCH)
        for url in urls:
            try:
                page_resp = requests.get(url, headers=COMMON_HEADERS, timeout=self.PAGE_FETCH_TIMEOUT)
            except requests.RequestException:
                continue  # esa página en concreto no respondió, seguimos con las demás
            if page_resp.status_code != 200:
                continue
            found_phones |= _extract_phones(page_resp.text)

        results = []
        for phone in sorted(found_phones):
            phone_entity = Entity(type="Phone", value=phone, properties={
                "origen": "encontrado en búsqueda web -- verificar el contexto de la página fuente",
            })
            results.append((phone_entity, "teléfono encontrado en búsqueda"))
        return results


@register
class OrganizationToPhoneHarvest(Transform):
    name = "Organization → Teléfonos (búsqueda web)"
    description = "Busca números de teléfono publicados de la empresa en páginas ya indexadas (gratis, sin key)"
    input_types = ["Organization"]
    uses_ddg = True

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    MAX_PAGES_TO_FETCH = 5
    PAGE_FETCH_TIMEOUT = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.SEARCH_URL,
            params={"q": f'"{entity.value}" "tel" OR "phone" OR "teléfono" OR "contacto"'},
            headers=COMMON_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        if is_ddg_blocked(resp.text):
            raise RuntimeError(DDG_BLOCK_MESSAGE)

        found_phones: Set[str] = set()
        found_phones |= _extract_phones(resp.text)

        urls = DorkToResults.parse_results(resp.text, limit=self.MAX_PAGES_TO_FETCH)
        for url in urls:
            try:
                page_resp = requests.get(url, headers=COMMON_HEADERS, timeout=self.PAGE_FETCH_TIMEOUT)
            except requests.RequestException:
                continue
            if page_resp.status_code != 200:
                continue
            found_phones |= _extract_phones(page_resp.text)

        results = []
        for phone in sorted(found_phones):
            phone_entity = Entity(type="Phone", value=phone, properties={
                "origen": f"encontrado en búsqueda web junto a '{entity.value}' -- verificar el contexto",
            })
            results.append((phone_entity, "posible teléfono de la organización"))
        return results


@register
class PhoneToWebSearch(Transform):
    name = "Phone → Búsqueda web (páginas que lo mencionan)"
    description = "Busca páginas públicas que mencionen este número -- búsqueda inversa pasiva, sin servicio de pago"
    input_types = ["Phone"]
    uses_ddg = True

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    MAX_RESULTS = 8

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.SEARCH_URL,
            params={"q": f'"{entity.value}"'},
            headers=COMMON_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        if is_ddg_blocked(resp.text):
            raise RuntimeError(DDG_BLOCK_MESSAGE)
        urls = DorkToResults.parse_results(resp.text, limit=self.MAX_RESULTS)

        if not urls:
            raise RuntimeError(
                f"No se encontró ninguna página pública que mencione '{entity.value}'. "
                "Es el resultado más habitual: la gran mayoría de teléfonos no están "
                "publicados en ninguna página indexada."
            )

        results = []
        for url in urls:
            results.append((Entity(type="URL", value=url, properties={
                "origen": f"página que menciona el teléfono {entity.value}",
            }), "página que menciona este teléfono"))
        return results
