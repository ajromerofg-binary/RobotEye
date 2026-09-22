"""
Transform de Wayback Machine (Internet Archive).

Usa la CDX API pública de web.archive.org: gratis, sin API key, estable
desde hace más de una década. Da acceso al índice completo de snapshots
archivados de un dominio -- útil en OSINT para encontrar contenido que ya
no está en la web en vivo (paneles viejos, ficheros borrados, versiones
anteriores de una web, subdominios que ya no resuelven, etc.).

Nota de fiabilidad: el propio Internet Archive sufrió una brecha de datos
y un ataque DDoS en 2024 que lo dejó caído temporalmente; el servicio se
recuperó, pero conviene manejar los fallos de red de esta transform sin
asumir que "caído" significa "sin snapshots" -- por eso los errores de
red se propagan como error explícito en vez de devolver una lista vacía.
"""
from typing import List, Tuple
from collections import Counter
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class DomainToWaybackSnapshots(Transform):
    name = "Domain → Snapshots archivados (Wayback Machine)"
    description = "Busca URLs archivadas del dominio en el Internet Archive (gratis, sin key)"
    input_types = ["Domain"]

    CDX_URL = "https://web.archive.org/cdx/search/cdx"
    MAX_RESULTS = 25

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.CDX_URL,
            params={
                "url": f"{entity.value}/*",
                "output": "json",
                "collapse": "urlkey",   # una entrada por URL única, no por cada captura repetida
                "limit": self.MAX_RESULTS,
                "filter": "statuscode:200",
            },
            headers={"User-Agent": "RobotEye-OSINT-Tool"},
            timeout=20,
        )
        if resp.status_code == 429:
            raise RuntimeError("Rate limit del Internet Archive alcanzado. Espera un poco y reintenta.")
        resp.raise_for_status()
        rows = resp.json()

        # La CDX API devuelve una lista de listas: la primera fila son los
        # nombres de columna, no un resultado.
        if not rows or len(rows) <= 1:
            return []

        columns = rows[0]
        try:
            idx_timestamp = columns.index("timestamp")
            idx_original = columns.index("original")
        except ValueError as ex:
            # La CDX API siempre devuelve estas columnas por defecto; si
            # alguna vez faltan (cambio de formato de la API, respuesta de
            # error servida como si fuera JSON válido...) mejor un mensaje
            # claro que un ValueError críptico -- bug real de manejo de
            # errores encontrado en la auditoría de esta ronda.
            raise RuntimeError(
                f"La respuesta de Wayback Machine no tiene el formato de columnas "
                f"esperado (falta '{ex}'). Puede que el servicio esté teniendo "
                "problemas temporales."
            )

        results = []
        for row in rows[1:]:
            timestamp = row[idx_timestamp]
            original_url = row[idx_original]
            snapshot_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
            url_entity = Entity(type="URL", value=snapshot_url, properties={
                "url_original": original_url,
                "fecha_snapshot": f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}",
            })
            results.append((url_entity, "snapshot archivado"))
        return results


@register
class DomainToWaybackSubdomains(Transform):
    name = "Domain → Subdominios históricos (Wayback Machine)"
    description = "Extrae subdominios que el Internet Archive ha visto alguna vez, aunque ya no resuelvan"
    input_types = ["Domain"]

    CDX_URL = "https://web.archive.org/cdx/search/cdx"
    MAX_ROWS = 2000  # filas crudas a inspeccionar, no subdominios finales

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.CDX_URL,
            params={
                "url": f"*.{entity.value}/*",
                "output": "json",
                "collapse": "urlkey",
                "limit": self.MAX_ROWS,
                "fl": "original",  # solo pedimos la columna de URL, respuesta más ligera
            },
            headers={"User-Agent": "RobotEye-OSINT-Tool"},
            timeout=20,
        )
        if resp.status_code == 429:
            raise RuntimeError("Rate limit del Internet Archive alcanzado. Espera un poco y reintenta.")
        resp.raise_for_status()
        rows = resp.json()

        if not rows or len(rows) <= 1:
            return []

        subdomain_counts = Counter()
        for row in rows[1:]:
            original_url = row[0]
            host = self._extract_host(original_url)
            if host and host != entity.value and host.endswith(entity.value):
                subdomain_counts[host] += 1

        results = []
        for host, _count in subdomain_counts.most_common(30):
            results.append((Entity(type="Domain", value=host), "subdominio histórico (Wayback)"))
        return results

    @staticmethod
    def _extract_host(url: str) -> str:
        # Evitamos depender de urllib.parse con URLs potencialmente mal formadas
        # que a veces trae el índice de Wayback; extracción manual y tolerante.
        without_scheme = url.split("://", 1)[-1]
        host = without_scheme.split("/", 1)[0]
        host = host.split(":", 1)[0]  # fuera el puerto si lo hay
        return host.lower().strip()
