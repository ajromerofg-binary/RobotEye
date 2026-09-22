"""
`Organization/Person → Comprobar en lista de sanciones OFAC (SDN)`:
consulta la lista de Nacionales Especialmente Designados (SDN) del
Tesoro de EEUU (OFAC) -- la lista de sanciones económicas más consultada
del mundo, e incluye tanto personas como empresas/entidades/barcos.

Fuente 100% pública y gratuita, sin API key: el fichero CSV crudo se
descarga directamente del propio Tesoro. Se investigó primero la
alternativa "oficial pero con key" (la Consolidated Screening List de
trade.gov, que junta 11 listas de EEUU en una sola API) -- se descartó
porque exige registrarse para conseguir una key, rompiendo el patrón de
cero configuración que mantiene el resto de la app. El fichero
`sdn.csv` crudo no exige nada de eso.

Detalle importante del formato: el fichero NO trae fila de cabecera --
hay que nombrar las 12 columnas a mano en el orden documentado por OFAC.
Los campos vacíos se marcan con el literal `-0-`, no con una cadena
vacía.

Aviso central de toda esta funcionalidad: una coincidencia de NOMBRE
nunca es una prueba de identidad -- nombres comunes, transliteraciones
distintas del mismo nombre, y homónimos hacen que esto sea, en el mejor
de los casos, una pista fuerte que hay que verificar a mano con más
datos (fecha de nacimiento, nacionalidad, documento), nunca una
confirmación automática.
"""
import csv
import io
from typing import List, Tuple, Optional

import requests

from core.entity_types import Entity
from core.transform_base import Transform, register

HEADERS = {"User-Agent": "RobotEye-OSINT-Tool contacto@sr-robot-labs.com"}
SDN_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"

# Orden real y documentado de las 12 columnas del fichero -- no trae
# cabecera propia, así que hay que declararlo aquí explícitamente.
_SDN_COLUMNS = [
    "ent_num", "sdn_name", "sdn_type", "program", "title",
    "call_sign", "vess_type", "tonnage", "grt", "vess_flag",
    "vess_owner", "remarks",
]

# Caché a nivel de módulo -- la lista SDN completa (15.000+ entradas) no
# tiene sentido volver a descargarla en cada nodo de la misma sesión.
_sdn_cache: Optional[List[dict]] = None


def _clean(value: str) -> str:
    """OFAC marca los campos vacíos con el literal '-0-', no con una
    cadena vacía -- hay que traducirlo explícitamente o acaba
    apareciendo tal cual en el panel de detalles, que es justo el tipo
    de literal-sin-sentido que ya se evitó en WHOIS/geolocalización en
    rondas anteriores de este mismo proyecto."""
    value = value.strip()
    return "" if value == "-0-" else value


def _get_sdn_list() -> List[dict]:
    global _sdn_cache
    if _sdn_cache is not None:
        return _sdn_cache
    resp = requests.get(SDN_CSV_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    reader = csv.reader(io.StringIO(resp.text))
    registros = []
    for row in reader:
        if len(row) < len(_SDN_COLUMNS):
            continue  # línea corta/corrupta -- se salta en vez de crashear toda la lista
        registros.append(dict(zip(_SDN_COLUMNS, row)))
    _sdn_cache = registros
    return registros


def _search_sdn(name: str) -> List[dict]:
    name_lower = name.strip().lower()
    if not name_lower:
        return []
    return [r for r in _get_sdn_list() if name_lower in r["sdn_name"].lower()]


def _run_sanctions_check(entity: Entity) -> List[Tuple[Entity, str]]:
    """Lógica compartida entre Organization y Person -- el fichero SDN
    mezcla ambos tipos, así que la búsqueda es idéntica salvo el tipo de
    entidad de origen."""
    coincidencias = _search_sdn(entity.value)

    if not coincidencias:
        entity.properties["ofac_sdn"] = "sin coincidencias en la lista SDN de OFAC"
        return []

    resumenes = []
    for r in coincidencias[:10]:
        programa = _clean(r["program"]) or "programa no especificado"
        remarks = _clean(r["remarks"])
        resumen = f"{r['sdn_name']} [{programa}]"
        if remarks:
            resumen += f" -- {remarks}"
        resumenes.append(resumen)

    entity.properties["ofac_sdn_total_coincidencias"] = len(coincidencias)
    entity.properties["ofac_sdn_coincidencias"] = " | ".join(resumenes)
    entity.properties["ofac_sdn_aviso"] = (
        "Coincidencia de NOMBRE, no de identidad -- verificar a mano con datos "
        "adicionales (fecha de nacimiento, nacionalidad, documento) antes de actuar."
    )
    return []


@register
class OrganizationToOFACSanctions(Transform):
    name = "Organization → Comprobar en lista de sanciones OFAC (SDN)"
    description = "Lista de sanciones del Tesoro de EEUU -- coincidencia por nombre, verificar SIEMPRE a mano"
    input_types = ["Organization"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        return _run_sanctions_check(entity)


@register
class PersonToOFACSanctions(Transform):
    name = "Person → Comprobar en lista de sanciones OFAC (SDN)"
    description = "Lista de sanciones del Tesoro de EEUU -- coincidencia por nombre, verificar SIEMPRE a mano"
    input_types = ["Person"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        return _run_sanctions_check(entity)
