"""
`Organization/Person → Noticias recientes (GDELT)`: busca menciones
recientes en prensa mundial usando el proyecto GDELT (Global Database of
Events, Language, and Tone), financiado académicamente y con una API
pública diseñada explícitamente para búsqueda programática -- monitoriza
medios de todo el mundo en 65+ idiomas, traducidos automáticamente al
inglés, con una ventana de búsqueda de los últimos ~3 meses.

Por qué esto y no el RSS de Google News (la alternativa más obvia):
técnicamente trivial de hacer, pero se investigó el robots.txt real de
news.google.com antes de escribir nada, y tiene
<code>Disallow: /</code> para <code>User-agent: *</code> con una lista
corta de excepciones que NO incluye <code>/rss/search</code> -- y ese
mismo fichero bloquea explícitamente a los rastreadores de Anthropic
(anthropic-ai, ClaudeBot, Claude-Web) en todo el dominio. Mismo criterio
que ya se aplicó con Ahmia: si el robots.txt dice que no, no se
construye un scraper contra eso, por trivial que sea saltárselo.

GDELT es harina de otro costal: una API pública gratuita, sin key,
construida explícitamente para esto (no un canal lateral tolerado).
Cortesía esperada por el propio proyecto: no más de 1 petición cada 5
segundos por IP.

Detalle de robustez documentado por el propio GDELT y verificado antes
de escribir el resto del código: ante una consulta rara o un problema
temporal del servicio, la API a veces responde con texto plano (o
vacío) en vez de JSON válido, incluso con código 200 -- hay que
protegerse explícitamente contra eso, no basta con comprobar el status.
"""
import requests
from typing import List, Tuple

from core.entity_types import Entity
from core.transform_base import Transform, register

HEADERS = {"User-Agent": "RobotEye-OSINT-Tool contacto@sr-robot-labs.com"}
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MAX_RESULTS = 10


def _search_news(name: str) -> List[dict]:
    params = {
        "query": f'"{name}"',
        "mode": "artlist",
        "format": "json",
        "maxrecords": MAX_RESULTS,
        "timespan": "1m",
        "sort": "datedesc",
    }
    resp = requests.get(GDELT_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(
            "GDELT no ha devuelto JSON válido -- puede ser un problema temporal "
            "del servicio, o una consulta con caracteres que no procesa bien. "
            "Reintenta más tarde."
        )
    return data.get("articles", []) or []


def _run_news_search(entity: Entity) -> List[Tuple[Entity, str]]:
    articulos = _search_news(entity.value)

    if not articulos:
        entity.properties["gdelt_noticias"] = "sin menciones recientes encontradas (último mes)"
        return []

    resumenes = []
    resultados = []
    for a in articulos:
        titulo = a.get("title") or "(sin título)"
        dominio = a.get("domain") or "?"
        fecha = a.get("seendate") or "?"
        resumenes.append(f"{titulo} [{dominio}, {fecha}]")
        url = a.get("url")
        if url:
            resultados.append((Entity(type="URL", value=url), "noticia reciente (GDELT)"))

    entity.properties["gdelt_total_noticias"] = len(articulos)
    entity.properties["gdelt_noticias"] = " | ".join(resumenes)
    return resultados


@register
class OrganizationToNews(Transform):
    name = "Organization → Noticias recientes (GDELT)"
    description = "Menciones de prensa mundial del último mes, vía GDELT -- gratis, sin key, sin scraping"
    input_types = ["Organization"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        return _run_news_search(entity)


@register
class PersonToNews(Transform):
    name = "Person → Noticias recientes (GDELT)"
    description = "Menciones de prensa mundial del último mes, vía GDELT -- gratis, sin key, sin scraping"
    input_types = ["Person"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        return _run_news_search(entity)
