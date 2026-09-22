"""
Tests del núcleo del proyecto (`core/`): el modelo de grafo, la
deduplicación de entidades, y la persistencia en JSON y SQLite.
"""
import pytest
from core.entity_types import Entity, VALID_TYPES
from core.graph_model import GraphModel


def test_add_entity_returns_id():
    model = GraphModel()
    e = Entity(type="Domain", value="ejemplo.com")
    entity_id = model.add_entity(e)
    assert entity_id == e.id
    assert model.get_entity(entity_id) is not None


def test_add_entity_deduplicates_by_type_and_value():
    """Bug histórico ('nodo fantasma'): al añadir dos veces la misma
    entidad (mismo tipo + valor), debe devolver el id de la YA existente,
    no crear una segunda. Si esto se rompe, aparecen nodos duplicados en
    el grafo cada vez que una transform encuentra el mismo dato dos veces."""
    model = GraphModel()
    e1 = Entity(type="Domain", value="ejemplo.com")
    e2 = Entity(type="Domain", value="ejemplo.com")  # mismo tipo+valor, instancia distinta
    id1 = model.add_entity(e1)
    id2 = model.add_entity(e2)
    assert id1 == id2
    assert len(model.all_entities()) == 1


def test_add_entity_does_not_deduplicate_different_types():
    """Mismo valor mismo, pero tipos distintos -> deben ser dos entidades
    separadas (ej. un Hash y un Username que coincidan como texto)."""
    model = GraphModel()
    model.add_entity(Entity(type="Domain", value="x"))
    model.add_entity(Entity(type="Username", value="x"))
    assert len(model.all_entities()) == 2


def test_remove_entity():
    model = GraphModel()
    e = Entity(type="Domain", value="ejemplo.com")
    entity_id = model.add_entity(e)
    model.remove_entity(entity_id)
    assert model.get_entity(entity_id) is None
    assert len(model.all_entities()) == 0


def test_add_relation_and_neighbors():
    model = GraphModel()
    e1 = Entity(type="Domain", value="x.com")
    e2 = Entity(type="IP", value="1.2.3.4")
    model.add_entity(e1)
    model.add_entity(e2)
    model.add_relation(e1.id, e2.id, "resuelve a")
    neighbors = model.neighbors(e1.id)
    assert len(neighbors) == 1
    assert neighbors[0].id == e2.id


def test_position_round_trip():
    model = GraphModel()
    e = Entity(type="Domain", value="x.com")
    model.add_entity(e)
    model.set_position(e.id, 123.5, -45.2)
    assert model.get_position(e.id) == (123.5, -45.2)


@pytest.mark.parametrize("entity_type", VALID_TYPES)
def test_json_persistence_round_trip_every_type(entity_type, tmp_path):
    """Cada uno de los tipos de entidad válidos debe sobrevivir un ciclo
    completo de guardado y carga en JSON, incluida su posición."""
    model = GraphModel()
    e = Entity(type=entity_type, value=f"valor_{entity_type}")
    model.add_entity(e)
    model.set_position(e.id, 10.0, 20.0)

    path = tmp_path / "proyecto.json"
    model.save_json(str(path))

    loaded = GraphModel()
    loaded.load_json(str(path))
    assert len(loaded.all_entities()) == 1
    loaded_entity = loaded.all_entities()[0]
    assert loaded_entity.type == entity_type
    assert loaded_entity.value == f"valor_{entity_type}"
    assert loaded.get_position(loaded_entity.id) == (10.0, 20.0)


def test_sqlite_persistence_round_trip_all_types(tmp_path):
    model = GraphModel()
    for t in VALID_TYPES:
        model.add_entity(Entity(type=t, value=f"v_{t}"))

    path = tmp_path / "proyecto.db"
    model.save_sqlite(str(path))

    loaded = GraphModel()
    loaded.load_sqlite(str(path))
    assert len(loaded.all_entities()) == len(VALID_TYPES)


def test_sqlite_without_positions_table_loads_without_error(tmp_path):
    """Compatibilidad hacia atrás: un SQLite de una versión anterior sin
    tabla `positions` debe cargar igualmente, sin posiciones guardadas."""
    import sqlite3
    path = tmp_path / "viejo.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE nodes (id TEXT, type TEXT, value TEXT, properties TEXT)")
    conn.execute("CREATE TABLE edges (source TEXT, target TEXT, label TEXT)")
    conn.execute(
        "INSERT INTO nodes VALUES (?, ?, ?, ?)",
        ("abc123", "Domain", "viejo.com", "{}"),
    )
    conn.commit()
    conn.close()

    model = GraphModel()
    model.load_sqlite(str(path))  # no debe lanzar excepción pese a faltar 'positions'
    assert len(model.all_entities()) == 1
