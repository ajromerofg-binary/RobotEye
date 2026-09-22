"""
Clase base que deben heredar todas las transforms.
Una transform recibe una Entity de entrada y devuelve una lista de
tuplas (Entity nueva, label de la relación).
"""
from abc import ABC, abstractmethod
from typing import List, Tuple
from core.entity_types import Entity


class Transform(ABC):
    name: str = "BaseTransform"
    description: str = ""
    input_types: List[str] = []   # tipos de entidad sobre los que aplica, ej ["Domain"]

    # Por defecto, toda transform en RobotEye es OSINT pasivo: consulta
    # fuentes públicas de terceros (DNS, crt.sh, Wayback, XposedOrNot...) sin
    # tocar directamente al objetivo. Las pocas que SÍ envían tráfico
    # dirigido al propio objetivo (ej. pedir su web para huella de
    # tecnologías) deben marcar requires_consent = True: la UI las agrupa
    # aparte en el menú contextual y exige una confirmación explícita de
    # autorización antes de ejecutarlas -- ver ui/main_window.py.
    requires_consent: bool = False

    # Marca explícita (no detectada por inspección de código, sería
    # frágil) para las transforms que consultan DuckDuckGo -- se usa para
    # escalonar su ejecución en "Ejecutar todas" y reducir el riesgo de
    # disparar el bloqueo por anomalías de tráfico (ver
    # dorking_transforms.py::is_ddg_blocked y ui/main_window.py). Si se
    # añade una transform nueva que consulte DDG, marcarla aquí también.
    uses_ddg: bool = False

    def applies_to(self, entity: Entity) -> bool:
        return entity.type in self.input_types

    @abstractmethod
    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        """
        Ejecuta la transform. Debe devolver una lista de
        (nueva_entidad, etiqueta_de_relacion).
        Lanzar excepción si algo falla; el runner la captura.
        """
        raise NotImplementedError


# Registro simple de transforms disponibles, se rellena en transforms/__init__.py
TRANSFORM_REGISTRY: List[Transform] = []


def register(transform_cls):
    """Decorador para registrar una transform automáticamente."""
    TRANSFORM_REGISTRY.append(transform_cls())
    return transform_cls
