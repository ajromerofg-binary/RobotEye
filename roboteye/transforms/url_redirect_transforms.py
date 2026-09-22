"""
`URL → Seguir redirecciones`: resuelve enlaces acortados/redirectores
(bit.ly, t.co, enlaces de tracking...) hasta su destino final. Muy útil en
OSINT: los resultados de dorks, redes sociales o documentos filtrados a
menudo traen enlaces acortados que ocultan el dominio real de destino.

No requiere consentimiento pese a "tocar" la URL directamente: seguir una
redirección es exactamente lo que hace cualquier navegador al abrir el
enlace, sin descargar ni interactuar con el contenido de la página final
más allá de leer la cabecera de respuesta.
"""
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import BROWSER_HEADERS
from transforms.organization_transforms import _root_domain


@register
class URLToFinalDestination(Transform):
    name = "URL → Seguir redirecciones (destino final)"
    description = "Resuelve enlaces acortados o de tracking hasta su URL final -- útil para bit.ly, t.co y similares"
    input_types = ["URL"]

    MAX_REDIRECTS = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        try:
            resp = requests.head(
                entity.value, headers=BROWSER_HEADERS, timeout=10,
                allow_redirects=True, verify=True,
            )
            # Algunos servidores no implementan bien HEAD (405/501) -- reintentamos con GET
            if resp.status_code in (405, 501):
                resp = requests.get(entity.value, headers=BROWSER_HEADERS, timeout=10, allow_redirects=True, stream=True)
        except requests.RequestException as ex:
            raise RuntimeError(f"No se pudo seguir la redirección de '{entity.value}': {ex}")

        final_url = resp.url
        saltos = len(resp.history)

        entity.properties.update({
            "url_destino_final": final_url,
            "saltos_de_redireccion": saltos,
            "codigo_http_final": resp.status_code,
        })

        if final_url == entity.value or saltos == 0:
            entity.properties["url_destino_final"] = "no redirige (URL ya es el destino final)"
            return []

        return [(Entity(type="URL", value=final_url, properties={
            "dominio": _root_domain(final_url),
        }), f"destino final tras {saltos} redirección(es)")]
