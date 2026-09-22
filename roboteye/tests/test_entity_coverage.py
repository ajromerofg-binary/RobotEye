"""
Convierte en test permanente la auditoría de cobertura que se ha repetido
a mano muchas veces a lo largo del desarrollo: ningún tipo de entidad
debe generarse por una transform sin que ninguna otra lo consuma como
entrada (un "callejón sin salida" en el grafo -- le pasó a `Organization`
en su momento, y a `ASN`/`Breach`/`Paste`/`URL` después).

Si este test falla tras añadir una transform nueva, no es necesariamente
un error: puede que el nuevo tipo de entidad sea intencionadamente un
punto final (ej. una entidad puramente informativa). En ese caso, añadir
el tipo a `INTENTIONALLY_TERMINAL` con una línea explicando por qué.
"""
import ast
import os

from transforms import TRANSFORM_REGISTRY
from core.entity_types import VALID_TYPES

TRANSFORMS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "transforms")

# Módulos FUERA de transforms/ que también generan entidades directamente
# (no como una Transform más, sino como parte de una acción de
# importación de un fichero) -- si no se incluyen aquí, el escáner basado
# en transforms/ los marcaría como "huérfanos" por error.
EXTRA_PRODUCER_FILES = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "email_analyzer.py"),
]

# Tipos que a día de hoy no tienen ninguna transform que los consuma, mas
# es una decisión de diseño consciente, no un hueco:
INTENTIONALLY_TERMINAL = {
    "EmailMessage",  # nodo-resumen de un correo analizado (Proyecto -> Analizar
                      # email sospechoso); todo lo interesante que cuelga de él
                      # (Email, Domain, IP, URL, Hash) ya son tipos normales con
                      # sus propias transforms -- el propio EmailMessage no se
                      # vuelve a usar como entrada de nada, es la "portada" del
                      # análisis, no un dato más a investigar por sí mismo.
}


def _produced_entity_types() -> set:
    """Recorre el AST de todos los módulos de transforms (y de los
    módulos listados en EXTRA_PRODUCER_FILES) buscando llamadas literales
    a Entity(type="X", ...) -- igual que el script de auditoría manual
    usado durante el desarrollo."""
    produced = set()
    paths = [os.path.join(TRANSFORMS_DIR, f) for f in os.listdir(TRANSFORMS_DIR)
             if f.endswith(".py") and f != "__init__.py"]
    paths += EXTRA_PRODUCER_FILES
    for path in paths:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Entity":
                for kw in node.keywords:
                    if kw.arg == "type" and isinstance(kw.value, ast.Constant):
                        produced.add(kw.value.value)
    return produced


def _consumed_entity_types() -> set:
    consumed = set()
    for t in TRANSFORM_REGISTRY:
        consumed.update(t.input_types)
    return consumed


def test_no_entity_type_is_a_dead_end():
    produced = _produced_entity_types()
    consumed = _consumed_entity_types()

    dead_ends = [
        t for t in VALID_TYPES
        if t in produced and t not in consumed and t not in INTENTIONALLY_TERMINAL
    ]
    assert not dead_ends, (
        f"Estos tipos de entidad se generan pero ninguna transform los consume: "
        f"{dead_ends}. O falta una transform de pivote, o hay que añadirlos a "
        f"INTENTIONALLY_TERMINAL con la justificación de por qué es correcto que "
        f"sean un punto final."
    )


def test_every_valid_type_has_at_least_one_transform():
    """Más laxo que el anterior: todo tipo debe tener AL MENOS una
    transform que lo consuma o lo produzca -- si no tiene ninguna de las
    dos, ese tipo es papel mojado en la app (nadie puede añadirle nada útil,
    ni sale de ningún sitio)."""
    produced = _produced_entity_types()
    consumed = _consumed_entity_types()
    orphaned = [t for t in VALID_TYPES if t not in produced and t not in consumed]
    assert not orphaned, f"Estos tipos no se producen NI se consumen en ninguna transform: {orphaned}"


def test_transform_registry_matches_entity_icons():
    """Todo tipo de VALID_TYPES debe tener su color e icono definidos en
    la UI -- si no, un nodo de ese tipo se renderiza con el color/icono
    por defecto en vez del suyo propio, un bug silencioso y fácil de no
    notar visualmente."""
    from ui.node_item import NODE_COLORS
    from core.entity_types import ENTITY_ICONS

    faltan_color = [t for t in VALID_TYPES if t not in NODE_COLORS]
    faltan_icono = [t for t in VALID_TYPES if t not in ENTITY_ICONS]
    assert not faltan_color, f"Tipos sin color de nodo definido: {faltan_color}"
    assert not faltan_icono, f"Tipos sin icono definido: {faltan_icono}"
