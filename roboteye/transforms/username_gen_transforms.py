"""
Transform de generación de usernames probables a partir de un nombre completo.

100% local, sin red: genera las combinaciones típicas que la gente usa al
registrarse en servicios (nombre.apellido, inicial+apellido, etc.) para
alimentar directamente las transforms de Username que ya existen
(GitHub, Reddit, comprobación pasiva del resto de redes).

Importante -- esto es un PUNTO DE PARTIDA para pivotar, no un resultado en
sí mismo: son candidatos sin verificar, no confirma que ninguno de ellos
exista de verdad. Por eso cada nodo generado lleva la propiedad 'origen'
dejándolo claro, para no confundirlo con un hallazgo real.
"""
import unicodedata
from typing import List, Tuple

from core.entity_types import Entity
from core.transform_base import Transform, register


def _normalize(text: str) -> str:
    """Quita acentos/diacríticos y deja solo alfanumérico en minúsculas
    (ej. 'José' -> 'jose'), que es como la gente suele adaptar su nombre
    al crear un username."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = decomposed.encode("ascii", "ignore").decode()
    return "".join(ch for ch in ascii_only if ch.isalnum()).lower()


@register
class PersonToUsernameGuesses(Transform):
    name = "Person → Usernames probables"
    description = "Genera permutaciones típicas de username a partir del nombre (candidatos sin verificar, cálculo local)"
    input_types = ["Person"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        parts = [p for p in entity.value.strip().split() if p]
        if len(parts) < 2:
            raise RuntimeError(
                f"'{entity.value}' no parece un nombre completo (nombre + apellido). "
                "Con un solo término no se pueden generar combinaciones útiles."
            )

        nombre = _normalize(parts[0])
        apellido = _normalize(parts[-1])
        if not nombre or not apellido:
            return []
        inicial = nombre[0]

        candidatos = {
            f"{nombre}.{apellido}",
            f"{nombre}{apellido}",
            f"{nombre}_{apellido}",
            f"{inicial}.{apellido}",
            f"{inicial}{apellido}",
            f"{apellido}.{nombre}",
            f"{apellido}{nombre}",
            f"{apellido}{inicial}",
        }

        results = []
        for username in sorted(candidatos):
            username_entity = Entity(type="Username", value=username, properties={
                "origen": "generado por permutación de nombre, NO verificado",
            })
            results.append((username_entity, "username probable"))
        return results
