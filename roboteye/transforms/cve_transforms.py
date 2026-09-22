"""
`Software → CVEs conocidas (NVD)`: busca en el NVD (National Vulnerability
Database, la base de datos oficial de vulnerabilidades del gobierno de
EEUU) posibles vulnerabilidades conocidas relacionadas con una tecnología
detectada por `Domain → Tecnologías web`.

Aviso de precisión importante, y por qué se diseñó así a propósito:
`Domain → Tecnologías web` detecta la PRESENCIA de una tecnología (ej.
"WordPress", "jQuery") a partir de patrones en el HTML/cabeceras, sin
extraer su número de versión exacto -- por eso esta transform busca por
palabra clave en la descripción de cada CVE (`keywordSearch`), no por CPE
exacto (`vendor:producto:versión`, que sí permitiría filtrar por
vulnerabilidad real y no solo por nombre). Esto da COBERTURA amplia a
cambio de PRECISIÓN: puede devolver CVEs de versiones antiguas ya
parcheadas hace años, o (más raro) de un producto homónimo distinto.

Cada resultado incluye su puntuación CVSS para que el usuario pueda
priorizar/descartar a mano -- tratar como punto de partida para investigar
manualmente qué versión corre el objetivo, nunca como confirmación de que
es vulnerable.

Sin API key: el NVD permite 5 peticiones cada 30 segundos sin ella (ver
nvd.nist.gov/developers), suficiente para consultas puntuales de OSINT.
"""
from typing import List, Tuple, Optional
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
MAX_RESULTS = 8


def _extract_cvss(cve: dict) -> Optional[Tuple[float, str]]:
    """Devuelve (puntuación, versión CVSS) probando v3.1 -> v3.0 -> v2, en
    ese orden de preferencia. El campo baseSeverity vive en un sitio
    distinto según la versión: dentro de cvssData en v3.x, pero como
    hermano de cvssData en v2 -- si no se distingue, se rompe la
    extracción para CVEs antiguos que solo tienen puntuación v2."""
    metrics = cve.get("metrics", {})

    for key, version in (("cvssMetricV31", "3.1"), ("cvssMetricV30", "3.0")):
        entries = metrics.get(key)
        if entries:
            score = entries[0].get("cvssData", {}).get("baseScore")
            if score is not None:
                return score, version

    entries = metrics.get("cvssMetricV2")
    if entries:
        score = entries[0].get("cvssData", {}).get("baseScore")
        if score is not None:
            return score, "2.0"

    return None


@register
class SoftwareToCVEs(Transform):
    name = "Software → CVEs conocidas (NVD)"
    description = "Busca vulnerabilidades conocidas por palabra clave en el NVD -- cobertura amplia, no precisión por versión exacta"
    input_types = ["Software"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            NVD_API_URL,
            params={"keywordSearch": entity.value, "resultsPerPage": MAX_RESULTS},
            headers={"User-Agent": "RobotEye-OSINT-Tool"},
            timeout=20,
        )
        if resp.status_code == 429:
            raise RuntimeError(
                "El NVD ha rechazado la petición por exceso de consultas (límite: 5 cada "
                "30 segundos sin API key). Espera medio minuto y reintenta."
            )
        if resp.status_code == 403:
            raise RuntimeError("El NVD ha rechazado la petición (403). Reintenta en unos segundos.")
        resp.raise_for_status()
        data = resp.json()

        vulnerabilities = data.get("vulnerabilities", [])
        if not vulnerabilities:
            raise RuntimeError(
                f"El NVD no devolvió ningún CVE para la palabra clave '{entity.value}'. "
                "No significa necesariamente que el software esté libre de vulnerabilidades "
                "conocidas -- puede que el nombre no coincida con cómo el NVD describe el "
                "producto en sus descripciones."
            )

        resumenes = []
        for item in vulnerabilities:
            cve = item.get("cve", {})
            cve_id = cve.get("id", "CVE-desconocido")
            cvss = _extract_cvss(cve)
            cvss_txt = f"CVSS {cvss[0]} v{cvss[1]}" if cvss else "sin puntuación CVSS"
            resumenes.append(f"{cve_id} ({cvss_txt})")

        entity.properties.update({
            "cve_total_encontrados": data.get("totalResults", len(vulnerabilities)),
            "cve_mostrados": ", ".join(resumenes),
            "cve_aviso": "búsqueda por palabra clave, no por versión exacta -- verificar a mano cuáles aplican de verdad",
        })
        return []  # enriquecimiento puro sobre el propio nodo Software, no genera nodos nuevos
