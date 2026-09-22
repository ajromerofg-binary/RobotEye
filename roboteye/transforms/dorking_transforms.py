"""
Transforms de Google Dorking.

Se dividen en dos pasos, a propósito:

  1) Domain -> Dork   : genera queries de dorking típicas para el dominio.
                         No hace ninguna petición de red, es pura generación local.
  2) Dork -> URL       : ejecuta esa query de verdad y devuelve las URLs encontradas.

¿Por qué no scrapear Google directamente? Porque banea IPs de scraping casi
al momento (captchas, bloqueos) y raspar sus resultados incumple sus términos
de servicio. La sintaxis de dorking (site:, filetype:, intitle:, inurl:...)
la soporta también DuckDuckGo HTML, que tolera scraping razonable y no
requiere API key, así que el paso 2 se ejecuta ahí. Los resultados no van a
ser idénticos a los de Google (índices distintos), pero la cobertura es
buena para uso de reconocimiento OSINT.
"""
from typing import List, Tuple
from urllib.parse import urlparse, parse_qs, unquote
import requests
from bs4 import BeautifulSoup

from core.entity_types import Entity
from core.transform_base import Transform, register


# Cabeceras de navegador real, compartidas por todas las transforms que
# consultan DuckDuckGo o descargan páginas públicas de terceros. Es
# importante que sean realistas: un User-Agent con una firma propia como
# "RobotEye/0.1" es precisamente lo que un sistema anti-bot (DuckDuckGo
# incluido) usa para identificar y bloquear peticiones automatizadas al
# momento -- lo contrario de lo que se pretende al evitar herramientas de
# pago. El resto de módulos importan esta misma constante en vez de
# definir la suya propia, para que un futuro ajuste solo haga falta
# hacerlo aquí.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://duckduckgo.com/",
}


# Marcadores conocidos de la página de bloqueo anti-bot de DuckDuckGo
# ("anomaly detection"). Es un mecanismo agresivo y bien documentado
# públicamente: puede bloquear una IP en cuestión de minutos si detecta
# un patrón de tráfico no humano (muchas peticiones automatizadas
# seguidas, como al probar varias transforms una tras otra). Es MUY
# distinto de "no hay resultados" -- si no se distingue, el usuario ve un
# "no se encontró nada" que parece decir que no existe el dato, cuando en
# realidad es DuckDuckGo bloqueando temporalmente. Todas las transforms
# basadas en DDG deben comprobar esto ANTES de asumir que la búsqueda
# genuinamente no encontró nada.
DDG_BLOCK_MARKERS = [
    "anomalydetectionblock",
    "unusual traffic",
    "detected unusual traffic",
    "type the characters you see",
]


def is_ddg_blocked(html: str) -> bool:
    html_lower = html.lower()
    return any(marker in html_lower for marker in DDG_BLOCK_MARKERS)


DDG_BLOCK_MESSAGE = (
    "DuckDuckGo ha bloqueado temporalmente esta IP por detectar tráfico "
    "automatizado (su sistema de detección de anomalías puede activarse en "
    "cuestión de minutos tras varias búsquedas seguidas -- es un mecanismo "
    "público y conocido, no un fallo de RobotEye). Esto explica que ayer "
    "funcionara y hoy no: no es que falte el dato, es que DDG está "
    "rechazando las peticiones automatizadas de esta IP por ahora. Suele "
    "desbloquearse solo tras un tiempo sin hacer búsquedas seguidas -- "
    "espera unos minutos u horas y reintenta."
)


# (operador de dork, descripción en español de qué intenta encontrar)
DORK_TEMPLATES = [
    ("filetype:pdf", "documentos PDF públicos"),
    ("filetype:xlsx", "hojas de cálculo públicas"),
    ("filetype:docx", "documentos Word públicos"),
    ("filetype:sql", "volcados SQL potencialmente expuestos"),
    ("filetype:log", "ficheros de log potencialmente expuestos"),
    ("filetype:env", "ficheros .env potencialmente expuestos"),
    ('intitle:"index of"', "listados de directorio abiertos"),
    ("inurl:admin", "paneles de administración"),
    ("inurl:login", "páginas de login expuestas"),
    ("inurl:wp-content", "instalación / plugins de WordPress"),
    ("inurl:config", "ficheros de configuración"),
    ('"confidential" OR "internal use only"', "documentos marcados como confidenciales"),
]


@register
class DomainToGoogleDorks(Transform):
    name = "Domain → Google Dorks (sugeridos)"
    description = "Genera queries de dorking típicas (site:, filetype:, inurl:...) para el dominio"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        results = []
        for operator, desc in DORK_TEMPLATES:
            query = f"site:{entity.value} {operator}"
            dork_entity = Entity(type="Dork", value=query, properties={"objetivo": desc})
            results.append((dork_entity, "dork sugerido"))
        return results


@register
class DorkToResults(Transform):
    name = "Ejecutar Dork (vía DuckDuckGo)"
    description = "Lanza la query del dork de verdad y trae las URLs encontradas"
    input_types = ["Dork"]
    uses_ddg = True

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    MAX_RESULTS = 15

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.SEARCH_URL,
            params={"q": entity.value},
            headers=BROWSER_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        if is_ddg_blocked(resp.text):
            raise RuntimeError(DDG_BLOCK_MESSAGE)
        urls = self.parse_results(resp.text, limit=self.MAX_RESULTS)
        return [(Entity(type="URL", value=u), "resultado dork") for u in urls]

    @staticmethod
    def parse_results(html: str, limit: int = 15) -> List[str]:
        """Extrae las URLs reales de una página de resultados de DuckDuckGo HTML.
        Separado en un staticmethod para poder testearlo sin red (con HTML de muestra).
        """
        soup = BeautifulSoup(html, "html.parser")
        urls = []
        seen = set()
        for a in soup.select("a.result__a"):
            href = a.get("href", "")
            real_url = href
            # DuckDuckGo envuelve el resultado real en un redirect propio:
            # //duckduckgo.com/l/?uddg=<url_codificada>&rut=...
            if "uddg=" in href:
                qs = parse_qs(urlparse(href).query)
                if qs.get("uddg"):
                    real_url = unquote(qs["uddg"][0])
            if real_url and real_url not in seen:
                seen.add(real_url)
                urls.append(real_url)
            if len(urls) >= limit:
                break
        return urls
