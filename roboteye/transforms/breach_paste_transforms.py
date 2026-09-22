"""
Transforms de pivote desde `Breach` y `Paste`.

Ambos tipos de entidad se generaban (vía XposedOrNot) pero no tenían ninguna
transform que los consumiera como entrada -- el mismo problema que tenía
`Organization` antes de la ronda anterior. A diferencia de otros pivotes de
este proyecto, estos dos NO hacen ninguna petición de red nueva: se limitan
a extraer un pivote útil de los datos que la transform original (XposedOrNot)
ya trajo y guardó como propiedades. Coste de red: cero.
"""
from typing import List, Tuple

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class BreachToOriginDomain(Transform):
    name = "Breach → Dominio de origen"
    description = "Extrae el dominio de la empresa afectada por esta brecha (dato ya obtenido, sin red nueva)"
    input_types = ["Breach"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        domain = entity.properties.get("dominio_origen")
        if not domain or not isinstance(domain, str):
            return []
        domain_entity = Entity(type="Domain", value=domain)
        return [(domain_entity, "dominio de la organización afectada")]


@register
class PasteToLink(Transform):
    name = "Paste → Enlace (si está disponible)"
    description = "Busca en los metadatos del paste algún enlace directo aprovechable (dato ya obtenido, sin red nueva)"
    input_types = ["Paste"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        # El esquema exacto de un Paste no está documentado públicamente por
        # XposedOrNot (ver aviso en xposedornot_transforms.py) -- por eso aquí
        # no asumimos ningún nombre de campo concreto, simplemente miramos si
        # ALGUNA propiedad ya guardada parece una URL utilizable.
        results = []
        seen = set()
        for value in entity.properties.values():
            if isinstance(value, str) and value.startswith(("http://", "https://")) and value not in seen:
                seen.add(value)
                results.append((Entity(type="URL", value=value), "enlace encontrado en metadatos del paste"))
        return results
