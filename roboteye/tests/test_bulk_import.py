"""
Tests de `guess_entity_type` (core/entity_types.py) y de la lógica de
importación masiva (`MainWindow._import_lines`).
"""
import pytest
from core.entity_types import guess_entity_type


@pytest.mark.parametrize("valor,esperado", [
    ("ejemplo.com", "Domain"),
    ("sub.ejemplo.co.uk", "Domain"),
    ("ana@ejemplo.com", "Email"),
    ("https://ejemplo.com/pagina", "URL"),
    ("http://ejemplo.com", "URL"),
    ("8.8.8.8", "IP"),
    ("2001:4860:4860::8888", "IP"),
    ("3.14", None),  # no debe confundirse con un dominio (TLD numérico)
    ("Ana Lopez", None),  # ambiguo -- nombre de persona
    ("Acme Corp", None),  # ambiguo -- nombre de empresa
    ("usuario123", None),  # ambiguo -- username
    ("FC:FB:FB:01:FA:21", None),  # MAC, no debe confundirse con nada
    ("con espacios.com", None),
    ("", None),
    ("   ", None),
])
def test_guess_entity_type(valor, esperado):
    assert guess_entity_type(valor) == esperado


def test_import_lines_autodetects_mixed_list(main_window):
    lineas = ["ejemplo.com", "ana@ejemplo.com", "8.8.8.8", "https://x.com/a"]
    added, duplicates = main_window._import_lines(lineas, default_type="Domain", autodetect=True)
    assert added == 4
    assert duplicates == 0
    tipos = {e.type for e in main_window.model.all_entities()}
    assert tipos == {"Domain", "Email", "IP", "URL"}
    assert len(main_window.model.all_entities()) == len(main_window.scene.node_items)


def test_import_lines_detects_duplicates_within_batch(main_window):
    added, duplicates = main_window._import_lines(["x.com", "x.com", "y.com"], default_type="Domain", autodetect=True)
    assert added == 2
    assert duplicates == 1
    assert len(main_window.model.all_entities()) == 2


def test_import_lines_autodetect_off_forces_default_type(main_window):
    main_window._import_lines(["ana@ejemplo.com", "8.8.8.8"], default_type="Username", autodetect=False)
    tipos = {e.type for e in main_window.model.all_entities()}
    assert tipos == {"Username"}


def test_import_lines_ambiguous_values_use_default_type(main_window):
    main_window._import_lines(["Ana Lopez", "Juan Perez"], default_type="Person", autodetect=True)
    tipos = {e.type for e in main_window.model.all_entities()}
    assert tipos == {"Person"}


def test_import_lines_against_existing_entity_is_deduplicated(main_window):
    """Importar un valor que YA existía en el grafo (añadido antes, no en
    este mismo lote) también debe detectarse como duplicado."""
    from core.entity_types import Entity
    existing = Entity(type="Domain", value="ya-existe.com")
    main_window.model.add_entity(existing)
    main_window.scene.add_entity_visual(existing)

    added, duplicates = main_window._import_lines(["ya-existe.com", "nuevo.com"], default_type="Domain", autodetect=True)
    assert added == 1
    assert duplicates == 1
