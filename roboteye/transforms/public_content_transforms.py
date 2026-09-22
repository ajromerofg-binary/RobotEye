"""
Dos capacidades relacionadas, ambas ejecutando de golpe búsquedas que
antes solo se generaban como dork para copiar y lanzar a mano
(`Domain → Google Dorks`, `Organization → Dorks de personas y contacto`):

- `Domain/Organization → Buscar documentos públicos`: ejecuta la
  búsqueda combinada de los mismos filetypes de documento que ya genera
  `Domain → Google Dorks` (PDF, XLSX, DOCX) y devuelve directamente las
  URLs encontradas como entidades `URL` -- que ya encadenan solas con
  `URL → Metadatos del documento` (autor, fecha de creación...).
- `Organization → Buscar publicaciones públicas`: busca menciones de la
  organización en plataformas que alojan publicaciones públicas
  (LinkedIn, X, Reddit) -- misma técnica que `PersonToSocialProfiles`:
  se consulta el índice ya público de DuckDuckGo, nunca se visita la red
  social directamente. Sin API de pago, sin acceder a ningún contenido
  privado -- solo lo que ya está indexado como público.

DuckDuckGo documenta que combinar `site:` con varios `filetype:` unidos
por `OR` funciona, aunque advierte que su sintaxis avanzada "no opera al
100% en todas las consultas" -- por eso cada resultado vacío se explica
con honestidad en vez de prometer cobertura perfecta.
"""
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import DorkToResults, BROWSER_HEADERS as COMMON_HEADERS, is_ddg_blocked, DDG_BLOCK_MESSAGE

SEARCH_URL = "https://html.duckduckgo.com/html/"

# Mismos filetypes que ya genera Domain -> Google Dorks, sin inventar
# cobertura nueva -- solo se automatiza la ejecución.
DOCUMENT_FILETYPES = ["pdf", "xlsx", "docx"]
_FILETYPE_CLAUSE = " OR ".join(f"filetype:{ft}" for ft in DOCUMENT_FILETYPES)

# Dominios que alojan publicaciones públicas indexables (no mensajes
# privados, no DMs) -- misma lista de plataformas ya usada en
# PersonToSocialProfiles para perfiles, aquí restringida a los patrones
# de URL de una publicación/post concreta, no de un perfil.
_PUBLIC_POST_SITES = ["linkedin.com/posts", "x.com", "twitter.com", "reddit.com"]
_SITE_CLAUSE = " OR ".join(f"site:{s}" for s in _PUBLIC_POST_SITES)


def _fetch_ddg_search(query: str) -> str:
    resp = requests.get(SEARCH_URL, params={"q": query}, headers=COMMON_HEADERS, timeout=15)
    resp.raise_for_status()
    if is_ddg_blocked(resp.text):
        raise RuntimeError(DDG_BLOCK_MESSAGE)
    return resp.text


@register
class DomainToDocumentSearch(Transform):
    name = "Domain → Buscar documentos públicos (PDF/XLSX/DOCX)"
    description = "Ejecuta de golpe la búsqueda de documentos que 'Google Dorks' solo sugiere -- sin copiar y pegar nada"
    input_types = ["Domain"]
    uses_ddg = True

    MAX_RESULTS = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        query = f"site:{entity.value} ({_FILETYPE_CLAUSE})"
        html = _fetch_ddg_search(query)
        urls = DorkToResults.parse_results(html, limit=self.MAX_RESULTS)

        if not urls:
            raise RuntimeError(
                f"No se encontró ningún documento PDF/XLSX/DOCX públicamente indexado "
                f"de '{entity.value}'. Es el resultado más habitual -- la mayoría de "
                "dominios no tienen documentos de este tipo indexados por buscadores."
            )

        return [(Entity(type="URL", value=u), "documento público encontrado") for u in urls]


@register
class OrganizationToDocumentSearch(Transform):
    name = "Organization → Buscar documentos públicos (PDF/XLSX/DOCX)"
    description = "Igual que la de Domain, pero buscando por nombre de empresa en vez de por dominio ya conocido"
    input_types = ["Organization"]
    uses_ddg = True

    MAX_RESULTS = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        query = f'"{entity.value}" ({_FILETYPE_CLAUSE})'
        html = _fetch_ddg_search(query)
        urls = DorkToResults.parse_results(html, limit=self.MAX_RESULTS)

        if not urls:
            raise RuntimeError(
                f"No se encontró ningún documento PDF/XLSX/DOCX públicamente indexado "
                f"para '{entity.value}'. Si ya conoces el dominio de la empresa, "
                "'Domain → Buscar documentos públicos' suele dar mejor cobertura al ir "
                "restringido a ese sitio concreto."
            )

        return [(Entity(type="URL", value=u), "documento público encontrado") for u in urls]


@register
class OrganizationToPublicPosts(Transform):
    name = "Organization → Buscar publicaciones públicas (LinkedIn, X, Reddit)"
    description = "Busca menciones en publicaciones ya públicas de esas plataformas -- nunca accede a mensajes privados"
    input_types = ["Organization"]
    uses_ddg = True

    MAX_RESULTS = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        query = f'"{entity.value}" ({_SITE_CLAUSE})'
        html = _fetch_ddg_search(query)
        urls = DorkToResults.parse_results(html, limit=self.MAX_RESULTS)

        if not urls:
            raise RuntimeError(
                f"No se encontró ninguna publicación pública que mencione "
                f"'{entity.value}' en LinkedIn, X o Reddit. Puede que no haya "
                "menciones indexadas, o que el nombre necesite ser más específico."
            )

        return [(Entity(type="URL", value=u), "publicación pública encontrada") for u in urls]
