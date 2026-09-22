"""
Transform crt.sh: Domain -> subdominios, vía Certificate Transparency logs.
Sin API key, endpoint público https://crt.sh/?q=...&output=json
"""
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import BROWSER_HEADERS


@register
class DomainToSubdomainsCrtSh(Transform):
    name = "Domain → Subdominios (crt.sh)"
    description = "Busca subdominios en Certificate Transparency logs (crt.sh)"
    input_types = ["Domain"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        results = []
        url = f"https://crt.sh/?q=%25.{entity.value}&output=json"
        # Bug real encontrado en la auditoría de esta ronda: esta petición
        # seguía usando la cabecera antigua "MaltegoClone/0.1" -- la misma
        # clase de bug que "RobotEye/0.1" (un User-Agent que se delata a sí
        # mismo como bot) que ya se corrigió en el resto del proyecto, pero
        # este archivo se quedó sin actualizar. Usa ahora BROWSER_HEADERS.
        resp = requests.get(url, timeout=15, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        data = resp.json()

        seen = set()
        for row in data:
            # .get(key) or "" -- no .get(key, "") -- crt.sh puede devolver
            # name_value: null explícito (no solo ausente), y con el default
            # posicional el .split() posterior crashearía con AttributeError.
            name_value = row.get("name_value") or ""
            for sub in name_value.split("\n"):
                sub = sub.strip().lstrip("*.")
                if sub and sub not in seen and sub != entity.value:
                    seen.add(sub)
                    results.append((Entity(type="Domain", value=sub), "subdominio (crt.sh)"))
        return results
