"""
`Domain/Organization/Email → Buscar en la dark web (Ahmia, manual)`.

Ahmia (ahmia.fi) es el índice de sitios .onion más recomendable para uso
profesional/OSINT: a diferencia de alternativas más permisivas como Torch
o Haystak, filtra activamente material ilegal a nivel de índice.

Su propio robots.txt PROHÍBE explícitamente el acceso automatizado a la
búsqueda -- comprobado directamente antes de escribir este módulo (una
petición de prueba a ahmia.fi/search/ fue rechazada citando su Disallow).
Por eso estas transforms NUNCA hacen ninguna petición de red: solo
preparan el enlace de búsqueda ya construido, listo para que el propio
usuario lo abra a mano en su navegador cuando quiera. Es exactamente lo
mismo que escribir la búsqueda uno mismo, solo que sin tener que teclearla.

Detalle de diseño importante: el enlace se guarda como PROPIEDAD del
propio nodo, nunca como una entidad `URL` nueva. Si fuera una entidad URL,
otras transforms genéricas de este proyecto que sí hacen peticiones reales
(`URL → Seguir redirecciones`, `URL → Emails y teléfonos`) podrían acabar
consultando ahmia.fi de forma automática si alguien las ejecutara sobre
ese nodo (o con "Ejecutar todas") -- justamente lo que se quiere evitar.
Guardarlo como texto en las propiedades hace que sea estructuralmente
imposible que ninguna transform lo toque sin que el usuario copie el
enlace y lo abra él mismo.
"""
from typing import List, Tuple
from urllib.parse import urlencode

from core.entity_types import Entity
from core.transform_base import Transform, register

AHMIA_SEARCH_BASE = "https://ahmia.fi/search/?"


def _build_ahmia_link(query: str) -> str:
    return AHMIA_SEARCH_BASE + urlencode({"q": query})


@register
class DomainToDarkWebSearch(Transform):
    name = "Domain → Buscar en la dark web (Ahmia, manual)"
    description = "Prepara el enlace de búsqueda en Ahmia para abrirlo tú mismo -- sin petición automática (respeta su robots.txt)"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        entity.properties["busqueda_dark_web_ahmia"] = _build_ahmia_link(entity.value)
        return []


@register
class OrganizationToDarkWebSearch(Transform):
    name = "Organization → Buscar en la dark web (Ahmia, manual)"
    description = "Prepara el enlace de búsqueda en Ahmia para abrirlo tú mismo -- sin petición automática (respeta su robots.txt)"
    input_types = ["Organization"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        entity.properties["busqueda_dark_web_ahmia"] = _build_ahmia_link(entity.value)
        return []


@register
class EmailToDarkWebSearch(Transform):
    name = "Email → Buscar en la dark web (Ahmia, manual)"
    description = "Prepara el enlace de búsqueda en Ahmia para abrirlo tú mismo -- sin petición automática (respeta su robots.txt)"
    input_types = ["Email"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        entity.properties["busqueda_dark_web_ahmia"] = _build_ahmia_link(entity.value)
        return []
