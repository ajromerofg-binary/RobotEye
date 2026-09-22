"""
`Organization/Person → Litigios federales (CourtListener)`: busca al
nombre como parte de un caso en expedientes de tribunales federales de
EEUU, vía la API de CourtListener (Free Law Project, un proyecto sin
ánimo de lucro que empezó como una clínica de Stanford en 2010).

Por qué CourtListener y no PACER directamente: PACER cobra ~0,10
$/página por cada documento consultado, e incluso solo para BUSCAR
(antes de ver nada) exige cuenta y tarjeta de crédito registrada. RECAP
(el archivo de PACER que mantiene CourtListener) se nutre de documentos
que otros usuarios ya han comprado y donado al archivo público -- sigue
sin ser 100% completo frente al PACER real, pero es genuinamente
gratuito y con una cobertura considerable (cientos de millones de
elementos).

Sobre la necesidad de API key: a diferencia de PatentsView y TSDR (ver
la investigación de patentes/marcas, descartada por exigir key), la API
de búsqueda de CourtListener SÍ funciona sin autenticar -- verificado
contra la documentación oficial antes de escribir código: 5.000
peticiones/día sin key, de sobra para el uso de RobotEye. La key
opcional solo sube ese límite (a 5.000/hora), no es necesaria para
funcionar.

Limitación honesta: esto cubre únicamente tribunales FEDERALES de EEUU
(no estatales, no de otros países), y la cobertura de RECAP depende de
qué documentos han donado otros usuarios de PACER al archivo público --
es amplia pero no exhaustiva. Una ausencia de resultados no es prueba de
que no haya litigios, solo de que no hay ninguno en RECAP con ese nombre
exacto como parte del caso.
"""
import requests
from typing import List, Tuple

from core.entity_types import Entity
from core.transform_base import Transform, register

HEADERS = {"User-Agent": "RobotEye-OSINT-Tool contacto@sr-robot-labs.com"}
COURTLISTENER_URL = "https://www.courtlistener.com/api/rest/v4/search/"
MAX_RESULTS = 10


def _search_litigation(name: str) -> dict:
    params = {
        "q": f'caseName:"{name}"',
        "type": "d",  # expedientes federales (dockets), sin metadatos de cada documento
    }
    resp = requests.get(COURTLISTENER_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _run_litigation_search(entity: Entity) -> List[Tuple[Entity, str]]:
    data = _search_litigation(entity.value)
    resultados_totales = data.get("count", 0)
    casos = data.get("results", []) or []

    if not casos:
        entity.properties["courtlistener_litigios"] = (
            "sin expedientes federales encontrados con ese nombre como parte del caso"
        )
        return []

    resumenes = []
    for caso in casos[:MAX_RESULTS]:
        nombre_caso = caso.get("caseName") or "(sin nombre de caso)"
        tribunal = caso.get("court") or caso.get("court_citation_string") or "?"
        fecha = caso.get("dateFiled") or "?"
        naturaleza = caso.get("suitNature") or ""
        resumen = f"{nombre_caso} [{tribunal}, {fecha}]"
        if naturaleza:
            resumen += f" -- {naturaleza}"
        resumenes.append(resumen)

    entity.properties["courtlistener_total_litigios"] = resultados_totales
    entity.properties["courtlistener_litigios"] = " | ".join(resumenes)
    entity.properties["courtlistener_aviso"] = (
        "Solo tribunales federales de EEUU, cobertura de RECAP no exhaustiva -- "
        "verificar cada caso a mano antes de sacar conclusiones."
    )
    return []


@register
class OrganizationToLitigation(Transform):
    name = "Organization → Litigios federales (CourtListener)"
    description = "Expedientes de tribunales federales de EEUU -- gratis, sin key, cobertura no exhaustiva (RECAP)"
    input_types = ["Organization"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        return _run_litigation_search(entity)


@register
class PersonToLitigation(Transform):
    name = "Person → Litigios federales (CourtListener)"
    description = "Expedientes de tribunales federales de EEUU -- gratis, sin key, cobertura no exhaustiva (RECAP)"
    input_types = ["Person"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        return _run_litigation_search(entity)
