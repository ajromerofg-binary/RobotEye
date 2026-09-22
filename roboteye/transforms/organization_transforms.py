"""
Transforms que parten de una entidad `Organization` (nombre de empresa).

Hasta ahora `Organization` solo existía como SALIDA de otras transforms
(WHOIS, análisis de teléfono...), nunca como entrada -- un callejón sin
salida en el grafo. Este módulo lo arregla con el puente más importante:
`Organization → Dominio probable`. En cuanto se tiene el dominio, el resto
de lo que se necesita (servidores de correo, WHOIS, subdominios, dorking...)
ya existe en el proyecto y encadena solo desde ahí.

Todo lo de este módulo es OSINT pasivo: ninguna transform toca el objetivo,
todas consultan un tercero (DuckDuckGo) o generan datos localmente.
"""
import re
import unicodedata
from typing import List, Tuple
from urllib.parse import urlparse, parse_qs, unquote
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import DorkToResults, BROWSER_HEADERS as COMMON_HEADERS, is_ddg_blocked, DDG_BLOCK_MESSAGE  # reutilizamos su parseo de resultados DDG y sus cabeceras realistas, ya probadas



# Dominios que son plataformas/directorios genéricos, nunca la web propia de
# la empresa -- los descartamos como candidato de "dominio probable".
GENERIC_PLATFORM_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "wikipedia.org", "crunchbase.com", "bloomberg.com",
    "glassdoor.com", "indeed.com", "duckduckgo.com", "google.com",
    "github.com", "medium.com", "yelp.com", "maps.google.com",
    "amazon.com", "play.google.com", "apps.apple.com",
}

# Sufijos legales habituales a limpiar al normalizar un nombre de empresa
LEGAL_SUFFIXES = re.compile(
    r"\b(s\.?l\.?u?\.?|s\.?a\.?u?\.?|sl|sa|inc\.?|llc|ltd\.?|corp\.?|gmbh|co\.?)\b\.?$",
    re.IGNORECASE,
)


def _root_domain(url: str) -> str:
    # .hostname (no .netloc) gestiona correctamente credenciales embebidas
    # (user:pass@host) y el puerto -- un split manual por ":" se equivoca
    # con URLs tipo "https://user:pass@x.com:8443/" (corta en el primer
    # ":", que es el de user:pass, no el del puerto). Bug real encontrado
    # y corregido durante la auditoría de código de esta ronda.
    host = urlparse(url).hostname
    if not host:
        return ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


@register
class OrganizationToProbableDomain(Transform):
    name = "Organization → Dominio probable (búsqueda web)"
    description = "Busca el nombre de la empresa y sugiere dominios candidatos -- verificar a mano"
    input_types = ["Organization"]
    uses_ddg = True

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    MAX_CANDIDATES = 3

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.SEARCH_URL,
            params={"q": entity.value},
            headers=COMMON_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        if is_ddg_blocked(resp.text):
            raise RuntimeError(DDG_BLOCK_MESSAGE)
        urls = DorkToResults.parse_results(resp.text, limit=15)

        if not urls:
            raise RuntimeError(
                f"DuckDuckGo no devolvió ningún resultado de búsqueda para '{entity.value}'. "
                "Puede deberse a que la consulta es muy genérica, a que DuckDuckGo esté "
                "limitando peticiones automatizadas en este momento (reintenta en unos "
                "segundos), o a que el nombre no aparezca indexado tal cual. Si conoces "
                "el dominio, añádelo a mano como entidad Domain."
            )

        seen_domains = []
        descartados_genericos = 0
        for url in urls:
            domain = _root_domain(url)
            if not domain:
                continue
            if domain in GENERIC_PLATFORM_DOMAINS or any(domain.endswith("." + g) for g in GENERIC_PLATFORM_DOMAINS):
                descartados_genericos += 1
                continue
            if domain not in seen_domains:
                seen_domains.append(domain)
            if len(seen_domains) >= self.MAX_CANDIDATES:
                break

        if not seen_domains:
            raise RuntimeError(
                f"Se encontraron {len(urls)} resultado(s) de búsqueda para '{entity.value}', pero "
                f"{descartados_genericos} de ellos eran directorios/plataformas genéricas "
                "(LinkedIn, Wikipedia, Crunchbase, Glassdoor...) -- ninguno parecía la web "
                "propia de la empresa. Puede que la empresa no tenga web propia indexada bajo "
                "ese nombre exacto, o que su dominio no aparezca en los primeros resultados. "
                "Si conoces el dominio, añádelo a mano como entidad Domain."
            )

        results = []
        for i, domain in enumerate(seen_domains):
            confianza = "media (primer resultado de búsqueda)" if i == 0 else "baja (verificar a mano)"
            domain_entity = Entity(type="Domain", value=domain, properties={"confianza": confianza})
            results.append((domain_entity, "dominio probable de la organización"))
        return results


# Patrones de dork orientados a encontrar personas y datos de contacto
# vinculados a una organización -- se generan como nodos Dork, igual que
# Domain → Google Dorks, para reutilizar la misma transform de ejecución
# (Ejecutar Dork vía DuckDuckGo) que ya existe.
PERSON_DORK_TEMPLATES = [
    ('site:linkedin.com/in "{org}"', "empleados con perfil de LinkedIn"),
    ('"{org}" "email" OR "contacto" OR "contact"', "páginas con datos de contacto"),
    ('"{org}" filetype:pdf "curriculum" OR "cv"', "CVs o currículums que mencionan la empresa"),
    ('"{org}" "tel:" OR "teléfono" OR "phone"', "páginas con números de teléfono asociados"),
    ('"{org}" intitle:"equipo" OR intitle:"team" OR intitle:"about us"', "páginas de equipo/quiénes somos"),
]


@register
class OrganizationToPersonDorks(Transform):
    name = "Organization → Dorks de personas y contacto"
    description = "Genera búsquedas para encontrar empleados, emails y teléfonos vinculados (sin red, ejecutar después)"
    input_types = ["Organization"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        results = []
        for template, objetivo in PERSON_DORK_TEMPLATES:
            query = template.format(org=entity.value)
            dork_entity = Entity(type="Dork", value=query, properties={"objetivo": objetivo})
            results.append((dork_entity, "dork de personas/contacto sugerido"))
        return results


@register
class OrganizationToPeople(Transform):
    name = "Organization → Personas vinculadas (LinkedIn)"
    description = "Busca perfiles de LinkedIn de personas vinculadas a la empresa y extrae nombres reales (verificar a mano)"
    input_types = ["Organization"]
    uses_ddg = True

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    MAX_PEOPLE = 8

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        query = f'site:linkedin.com/in "{entity.value}"'
        resp = requests.get(self.SEARCH_URL, params={"q": query}, headers=COMMON_HEADERS, timeout=15)
        resp.raise_for_status()
        if is_ddg_blocked(resp.text):
            raise RuntimeError(DDG_BLOCK_MESSAGE)
        items = _parse_ddg_titles(resp.text, limit=20)

        if not items:
            raise RuntimeError(
                f"DuckDuckGo no devolvió ningún resultado para perfiles de LinkedIn "
                f"relacionados con '{entity.value}'. LinkedIn bloquea agresivamente la "
                "indexación de sus propios perfiles por terceros, así que esto es "
                "habitual incluso para empresas grandes con muchos empleados -- no "
                "significa necesariamente que no haya nadie. Prueba también con "
                "'Dorks de personas y contacto' para otras fuentes."
            )

        results = []
        seen_names = set()
        for title, url in items:
            if "linkedin.com/in/" not in url.lower():
                continue  # filtra páginas de empresa/empleo que a veces cuelan pese al site:
            name = _extract_person_name_from_title(title)
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            person_entity = Entity(type="Person", value=name, properties={
                "origen": f"perfil de LinkedIn encontrado buscando '{entity.value}' -- verificar a mano",
                "linkedin_url": url,
                "confianza": "media (nombre extraído de un resultado de búsqueda, no confirmado)",
            })
            results.append((person_entity, "posible empleado (LinkedIn)"))
            if len(results) >= self.MAX_PEOPLE:
                break

        if not results:
            raise RuntimeError(
                f"Se encontraron {len(items)} resultado(s) para '{entity.value}', pero "
                "ninguno tenía forma de perfil individual de LinkedIn con un nombre "
                "reconocible -- puede que fueran páginas de empresa o de empleo."
            )
        return results


def _parse_ddg_titles(html: str, limit: int = 15) -> list:
    """Como DorkToResults.parse_results, pero conservando también el título
    del resultado (necesario aquí para extraer el nombre de la persona;
    el resto de transforms del proyecto solo necesitan la URL)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.select("a.result__a"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        real_url = href
        if "uddg=" in href:
            qs = parse_qs(urlparse(href).query)
            if qs.get("uddg"):
                real_url = unquote(qs["uddg"][0])
        if title and real_url:
            items.append((title, real_url))
        if len(items) >= limit:
            break
    return items


def _extract_person_name_from_title(title: str) -> str:
    """Los resultados de LinkedIn suelen tener el formato 'Nombre Apellido -
    Puesto - Empresa | LinkedIn' o simplemente 'Nombre Apellido | LinkedIn'.
    Nos quedamos con el primer segmento, que casi siempre es el nombre, y
    descartamos candidatos que claramente no lo son (muy cortos/largos,
    con dígitos, etc.)."""
    candidate = title
    for sep in (" - ", " | ", " – ", " en LinkedIn"):
        if sep in candidate:
            candidate = candidate.split(sep)[0].strip()
    candidate = candidate.strip()

    words = candidate.split()
    if not (2 <= len(words) <= 5):
        return ""
    if any(ch.isdigit() for ch in candidate):
        return ""
    return candidate


def _normalize_org_name(name: str) -> str:
    cleaned = LEGAL_SUFFIXES.sub("", name).strip()
    # Transliteración a ASCII (tildes, eñes...): ningún username real de
    # GitHub/Reddit/redes sociales admite "ñ" o vocales acentuadas -- sin
    # esto, "Telefónica España" generaría "telefónica-españa", un
    # candidato que nadie podría registrar de verdad en ningún sitio.
    decomposed = unicodedata.normalize("NFKD", cleaned)
    cleaned = decomposed.encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)  # fuera puntuación residual (&, comas...)
    return cleaned.strip()


@register
class OrganizationToUsernameGuesses(Transform):
    name = "Organization → Usernames probables"
    description = "Genera candidatos de handle de marca para redes sociales (candidatos sin verificar, cálculo local)"
    input_types = ["Organization"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        cleaned = _normalize_org_name(entity.value)
        if not cleaned:
            return []

        words = cleaned.split()
        joined = "".join(words).lower()
        hyphened = "-".join(words).lower()
        initials = "".join(w[0] for w in words).lower() if len(words) > 1 else joined

        candidatos = {joined, hyphened, initials}
        candidatos.discard("")
        # Filtro de calidad: descarta iniciales demasiado cortas para ser
        # útiles (ruido tipo "sl"), PERO nunca si eso dejara el conjunto
        # vacío -- para una marca corta de verdad (ej. "H&M" -> "hm"), un
        # candidato de 2 letras es mejor que ningún candidato en absoluto.
        candidatos_filtrados = {c for c in candidatos if len(c) >= 3}
        candidatos = candidatos_filtrados if candidatos_filtrados else candidatos

        results = []
        for username in sorted(candidatos):
            username_entity = Entity(type="Username", value=username, properties={
                "origen": "generado a partir del nombre de la organización, NO verificado",
            })
            results.append((username_entity, "posible handle de marca"))
        return results
