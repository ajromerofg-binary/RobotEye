"""
*** ZONA GRIS: esta transform SÍ toca el objetivo ***

Detección de tecnologías web (estilo Wappalyzer/BuiltWith): pide la home
del dominio por HTTP y analiza cabeceras + patrones del HTML (rutas de
wp-content, metatags generator, huellas de frameworks JS...) para
identificar CMS/frameworks/servidor en uso.

Por qué vive en su propio módulo y no junto al resto de transforms: todo
lo demás en RobotEye (DNS, WHOIS, crt.sh, Wayback, XposedOrNot, Team Cymru,
Shodan InternetDB, keys.openpgp.org...) consulta ÚNICAMENTE fuentes
públicas de terceros -- nunca se envía tráfico directo al objetivo que
estás investigando. Esto es distinto: es una petición HTTP normal, el
mismo "nivel de contacto" que hace cualquier navegador al visitar una web,
pero va dirigida al objetivo en sí, no a un tercero. Esa es la línea que
separa OSINT pasivo de reconocimiento activo.

Por eso esta transform:
  1. Vive en su propio fichero, claramente marcado (este docstring).
  2. Declara `requires_consent = True` (ver core/transform_base.py).
  3. La UI la agrupa en una sección aparte del menú contextual y exige una
     confirmación explícita de autorización antes de ejecutarla -- ver
     ui/main_window.py, run_transform_with_consent().

No hace nada más agresivo que cargar la página de inicio una vez: no
fuerza rutas, no prueba credenciales, no manda payloads. Aun así, sigue
siendo tráfico dirigido, y por eso el aviso.
"""
import re
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import BROWSER_HEADERS


# (nombre de la tecnología, patrón de detección, dónde se busca)
TECH_SIGNATURES = [
    ("WordPress", re.compile(r"wp-content|wp-includes|/wp-json/", re.I), "html"),
    ("Drupal", re.compile(r"Drupal\.settings|/sites/default/files/", re.I), "html"),
    ("Joomla", re.compile(r"/media/jui/|Joomla!", re.I), "html"),
    ("React", re.compile(r"react(-dom)?[.\-]?(min\.)?js|data-reactroot", re.I), "html"),
    ("Vue.js", re.compile(r"vue(\.min)?\.js|data-v-app|__vue__", re.I), "html"),
    ("Angular", re.compile(r"ng-version|angular(\.min)?\.js", re.I), "html"),
    ("jQuery", re.compile(r"jquery(-[\d.]+)?(\.min)?\.js", re.I), "html"),
    ("Bootstrap", re.compile(r"bootstrap(\.min)?\.(css|js)", re.I), "html"),
    ("Cloudflare", re.compile(r"cloudflare", re.I), "server_header"),
    ("Nginx", re.compile(r"nginx", re.I), "server_header"),
    ("Apache", re.compile(r"apache", re.I), "server_header"),
    ("IIS", re.compile(r"iis|microsoft-iis", re.I), "server_header"),
    ("PHP", re.compile(r"php", re.I), "powered_by_header"),
    ("ASP.NET", re.compile(r"asp\.net", re.I), "powered_by_header"),
]


@register
class DomainToWebTechnologies(Transform):
    name = "Domain → Tecnologías web (estilo Wappalyzer)"
    description = "Pide la home del dominio y detecta CMS/frameworks/servidor -- TOCA el objetivo, requiere confirmación"
    input_types = ["Domain"]
    requires_consent = True

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        headers = BROWSER_HEADERS
        url = f"https://{entity.value}"
        try:
            resp = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
        except requests.exceptions.SSLError:
            url = f"http://{entity.value}"
            try:
                resp = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
            except requests.RequestException as ex:
                raise RuntimeError(f"No se pudo conectar a '{entity.value}' ni por HTTPS ni por HTTP: {ex}")
        except requests.RequestException as ex:
            raise RuntimeError(f"No se pudo conectar a '{entity.value}': {ex}")

        html = resp.text
        server_header = resp.headers.get("Server", "")
        powered_by = resp.headers.get("X-Powered-By", "")
        sources = {"html": html, "server_header": server_header, "powered_by_header": powered_by}

        detected = [name for name, pattern, source in TECH_SIGNATURES if pattern.search(sources[source])]

        entity.properties.update({
            "servidor_http": server_header or "no revelado",
            "x_powered_by": powered_by or "no revelado",
            "tecnologias_detectadas": ", ".join(detected) if detected else "ninguna identificada por firma",
            "codigo_http": resp.status_code,
            "url_analizada": url,
        })

        # Además de guardarlo como texto (comportamiento original), cada
        # tecnología detectada se genera también como entidad Software --
        # el pivote necesario para poder encadenar con
        # `Software → CVEs conocidas (NVD)`.
        return [
            (Entity(type="Software", value=name, properties={
                "origen": f"detectado por firma en {entity.value}",
            }), "tecnología detectada")
            for name in detected
        ]
