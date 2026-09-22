"""
Transforms de enriquecimiento de `Person`: a partir de un nombre, buscar su
posible teléfono, email, perfiles en redes sociales, empresa de trabajo y
ciudad.

Mismo nivel de contacto pasivo que el resto de transforms basadas en
DuckDuckGo del proyecto: solo se consulta a un tercero (el buscador) y se
leen páginas públicas ya indexadas -- nunca se toca a la persona
directamente. Por eso ninguna de estas transforms requiere consentimiento.

*** Aviso de honestidad importante ***
Buscar por NOMBRE es inherentemente ambiguo: un nombre común (ej. "Ana
García", "John Smith") puede coincidir con decenas de personas distintas
que no tienen nada que ver entre sí. A diferencia de buscar por email o
dominio (identificadores casi únicos), aquí el propio punto de partida ya
es ambiguo -- todo lo que devuelven estas transforms es una PISTA a
verificar, nunca un dato confirmado. Cuantos más datos de contexto tenga
ya el grafo (ej. la empresa donde se cree que trabaja), más fácil es
descartar coincidencias falsas a mano.
"""
import re
from typing import List, Tuple, Set
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import BROWSER_HEADERS, DorkToResults, is_ddg_blocked, DDG_BLOCK_MESSAGE
from transforms.phone_harvest_transforms import _extract_phones

SEARCH_URL = "https://html.duckduckgo.com/html/"

# Regex de email genérico (sin dominio conocido -- a diferencia de
# email_harvest_transforms._extract_emails, que exige un dominio concreto,
# aquí no lo tenemos porque partimos solo de un nombre de persona).
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Dominios de redes sociales que reconocemos como perfil directo de persona
SOCIAL_DOMAIN_PATTERNS = [
    ("LinkedIn", "linkedin.com/in/"),
    ("X (Twitter)", "twitter.com/"),
    ("X (Twitter)", "x.com/"),
    ("Instagram", "instagram.com/"),
    ("Facebook", "facebook.com/"),
]


def _extract_any_email(text: str) -> Set[str]:
    return {m.group(0).lower() for m in EMAIL_PATTERN.finditer(text)}


def _fetch_ddg(query: str):
    resp = requests.get(SEARCH_URL, params={"q": query}, headers=BROWSER_HEADERS, timeout=15)
    resp.raise_for_status()
    if is_ddg_blocked(resp.text):
        raise RuntimeError(DDG_BLOCK_MESSAGE)
    return resp.text


@register
class PersonToEmails(Transform):
    name = "Person → Emails (búsqueda web)"
    description = "Busca direcciones de email publicadas junto al nombre de la persona (verificar a mano -- nombres ambiguos)"
    input_types = ["Person"]
    uses_ddg = True

    MAX_PAGES_TO_FETCH = 5
    PAGE_FETCH_TIMEOUT = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        html = _fetch_ddg(f'"{entity.value}" email')
        found: Set[str] = set()
        found |= _extract_any_email(html)

        urls = DorkToResults.parse_results(html, limit=self.MAX_PAGES_TO_FETCH)
        for url in urls:
            try:
                page = requests.get(url, headers=BROWSER_HEADERS, timeout=self.PAGE_FETCH_TIMEOUT)
            except requests.RequestException:
                continue
            if page.status_code != 200:
                continue
            found |= _extract_any_email(page.text)

        if not found:
            raise RuntimeError(
                f"No se encontró ningún email publicado junto a '{entity.value}'. "
                "Con un nombre de persona (a diferencia de un dominio) es habitual no "
                "encontrar nada si no hay páginas públicas que lo mencionen junto a un "
                "email -- no significa que la persona no tenga email, solo que no está "
                "indexado así."
            )

        results = []
        for email in sorted(found):
            e = Entity(type="Email", value=email, properties={
                "origen": f"encontrado en búsqueda web junto a '{entity.value}' -- verificar que es la persona correcta",
                "confianza": "baja (nombre de persona, alta ambigüedad)",
            })
            results.append((e, "posible email de la persona"))
        return results


@register
class PersonToPhones(Transform):
    name = "Person → Teléfonos (búsqueda web)"
    description = "Busca números de teléfono publicados junto al nombre de la persona (verificar a mano -- nombres ambiguos)"
    input_types = ["Person"]
    uses_ddg = True

    MAX_PAGES_TO_FETCH = 5
    PAGE_FETCH_TIMEOUT = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        html = _fetch_ddg(f'"{entity.value}" telefono OR teléfono OR phone OR contacto')
        found: Set[str] = set()
        found |= _extract_phones(html)

        urls = DorkToResults.parse_results(html, limit=self.MAX_PAGES_TO_FETCH)
        for url in urls:
            try:
                page = requests.get(url, headers=BROWSER_HEADERS, timeout=self.PAGE_FETCH_TIMEOUT)
            except requests.RequestException:
                continue
            if page.status_code != 200:
                continue
            found |= _extract_phones(page.text)

        if not found:
            raise RuntimeError(
                f"No se encontró ningún teléfono publicado junto a '{entity.value}'. "
                "Es el resultado más habitual: la gran mayoría de personas no tienen su "
                "teléfono en ninguna página pública indexada."
            )

        results = []
        for phone in sorted(found):
            e = Entity(type="Phone", value=phone, properties={
                "origen": f"encontrado en búsqueda web junto a '{entity.value}' -- verificar que es la persona correcta",
                "confianza": "baja (nombre de persona, alta ambigüedad)",
            })
            results.append((e, "posible teléfono de la persona"))
        return results


@register
class PersonToSocialProfiles(Transform):
    name = "Person → LinkedIn y redes sociales (búsqueda web)"
    description = "Busca perfiles de LinkedIn, X, Instagram y Facebook con este nombre (verificar a mano -- nombres ambiguos)"
    input_types = ["Person"]
    uses_ddg = True

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        html = _fetch_ddg(f'"{entity.value}"')
        urls = DorkToResults.parse_results(html, limit=20)

        results = []
        seen = set()
        for url in urls:
            url_lower = url.lower()
            for plataforma, patron in SOCIAL_DOMAIN_PATTERNS:
                if patron in url_lower and url not in seen:
                    seen.add(url)
                    e = Entity(type="URL", value=url, properties={
                        "plataforma": plataforma,
                        "confianza": "baja (nombre de persona, verificar que es ella)",
                    })
                    results.append((e, f"posible perfil de {plataforma}"))
                    break

        if not results:
            raise RuntimeError(
                f"No se encontró ningún perfil de LinkedIn/X/Instagram/Facebook para "
                f"'{entity.value}' entre los resultados de búsqueda. Puede que el nombre "
                "sea poco común en esas redes, o que DuckDuckGo no tenga indexado ese "
                "perfil concreto."
            )
        return results


def _extract_company_from_title(title: str) -> str:
    """Inverso de organization_transforms._extract_person_name_from_title:
    los títulos de LinkedIn suelen tener el formato 'Nombre Apellido -
    Puesto - Empresa | LinkedIn'. Aquí nos interesa el ÚLTIMO segmento
    antes de '| LinkedIn', que casi siempre es la empresa."""
    if "|" in title:
        before_pipe = title.split("|")[0].strip()
    else:
        before_pipe = title.strip()
    parts = [p.strip() for p in before_pipe.split(" - ") if p.strip()]
    if len(parts) < 2:
        return ""  # solo el nombre, sin puesto ni empresa -- no hay nada que extraer
    company = parts[-1]
    if any(ch.isdigit() for ch in company) or len(company) < 2:
        return ""
    return company


def _extract_city_from_snippet(snippet: str) -> str:
    """Heurística best-effort: los snippets de perfil de LinkedIn a veces
    muestran la ubicación al principio en formato 'Ciudad, Región, País'.
    Es frágil por diseño -- si no encuentra un patrón claro, no devuelve
    nada en vez de forzar un candidato dudoso."""
    match = re.match(r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñ.]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ.]+)*),\s?([A-ZÁÉÍÓÚÑ])", snippet)
    if match:
        return match.group(1)
    return ""


def _parse_ddg_titles_and_snippets(html: str, limit: int = 15):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for result_div in soup.select(".result, .web-result"):
        a = result_div.select_one("a.result__a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        real_url = href
        if "uddg=" in href:
            qs = parse_qs(urlparse(href).query)
            if qs.get("uddg"):
                real_url = unquote(qs["uddg"][0])
        snippet_el = result_div.select_one(".result__snippet")
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        if title and real_url:
            items.append((title, real_url, snippet))
        if len(items) >= limit:
            break
    return items


@register
class PersonToEmployerAndCity(Transform):
    name = "Person → Empresa y ciudad (LinkedIn)"
    description = "Busca el perfil de LinkedIn de la persona y extrae empresa y ciudad si aparecen (heurística, verificar a mano)"
    input_types = ["Person"]
    uses_ddg = True

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        html = _fetch_ddg(f'site:linkedin.com/in "{entity.value}"')
        items = _parse_ddg_titles_and_snippets(html, limit=15)

        if not items:
            raise RuntimeError(
                f"DuckDuckGo no devolvió ningún resultado de LinkedIn para "
                f"'{entity.value}'. LinkedIn bloquea agresivamente la indexación de "
                "sus perfiles por terceros, así que esto es habitual incluso para "
                "personas con perfil público."
            )

        results = []
        empresa_encontrada = False
        for title, url, snippet in items:
            if "linkedin.com/in/" not in url.lower():
                continue
            empresa = _extract_company_from_title(title)
            if empresa:
                empresa_encontrada = True
                e = Entity(type="Organization", value=empresa, properties={
                    "origen": f"extraída del perfil de LinkedIn de '{entity.value}' -- verificar a mano",
                    "confianza": "media (nombre extraído de un resultado de búsqueda, no confirmado)",
                })
                results.append((e, "posible empresa de la persona"))

            ciudad = _extract_city_from_snippet(snippet) if snippet else ""
            if ciudad:
                entity.properties["ciudad_probable"] = ciudad
                entity.properties["ciudad_origen"] = "extraída del snippet de un resultado de LinkedIn -- heurística, poco fiable"

            if empresa or ciudad:
                break  # nos quedamos con el primer perfil que dé algún dato útil

        if not empresa_encontrada and "ciudad_probable" not in entity.properties:
            raise RuntimeError(
                f"Se encontraron resultados de LinkedIn para '{entity.value}', pero "
                "ninguno tenía un formato de título/snippet del que extraer empresa o "
                "ciudad con confianza razonable."
            )
        return results
