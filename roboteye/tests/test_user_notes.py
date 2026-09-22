"""
Tests de las notas manuales del usuario en un nodo: el campo
`Entity.user_note`, su persistencia en JSON/SQLite (incluida la
compatibilidad hacia atrás con proyectos guardados antes de este campo),
el flujo de guardado desde la interfaz, y su aparición en los informes
HTML/PDF.
"""
import sqlite3
from core.entity_types import Entity
from core.graph_model import GraphModel
from core.report_generator import generate_html_report, generate_pdf_report


def test_entity_user_note_defaults_to_empty_string():
    e = Entity(type="Domain", value="x.com")
    assert e.user_note == ""


def test_json_round_trip_preserves_user_note(tmp_path):
    model = GraphModel()
    e = Entity(type="Domain", value="x.com", user_note="confirmado a mano")
    model.add_entity(e)
    path = str(tmp_path / "p.json")
    model.save_json(path)

    loaded = GraphModel()
    loaded.load_json(path)
    assert loaded.all_entities()[0].user_note == "confirmado a mano"


def test_sqlite_round_trip_preserves_user_note(tmp_path):
    model = GraphModel()
    e = Entity(type="Domain", value="x.com", user_note="pendiente de verificar con el cliente")
    model.add_entity(e)
    path = str(tmp_path / "p.db")
    model.save_sqlite(path)

    loaded = GraphModel()
    loaded.load_sqlite(path)
    assert loaded.all_entities()[0].user_note == "pendiente de verificar con el cliente"


def test_sqlite_backward_compatibility_without_user_note_column(tmp_path):
    """Un proyecto SQLite guardado ANTES de que existiera este campo no
    tiene la columna user_note -- debe cargar igualmente, con nota vacía
    por defecto, en vez de fallar."""
    path = str(tmp_path / "viejo.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE nodes (id TEXT, type TEXT, value TEXT, properties TEXT)")
    conn.execute("CREATE TABLE edges (source TEXT, target TEXT, label TEXT)")
    conn.execute("INSERT INTO nodes VALUES (?, ?, ?, ?)", ("abc", "Domain", "viejo.com", "{}"))
    conn.commit()
    conn.close()

    model = GraphModel()
    model.load_sqlite(path)  # no debe lanzar excepción
    assert model.all_entities()[0].user_note == ""


def test_show_entity_details_loads_note_into_notes_box(main_window):
    e = Entity(type="Domain", value="x.com", user_note="ya revisado")
    main_window.model.add_entity(e)
    main_window.scene.add_entity_visual(e)

    main_window.show_entity_details(e)
    assert main_window.notes_box.toPlainText() == "ya revisado"


def test_switching_selection_shows_correct_note_per_entity(main_window):
    """Cambiar de nodo seleccionado debe mostrar la nota de CADA entidad,
    nunca arrastrar la del anterior."""
    e1 = Entity(type="Domain", value="x.com", user_note="nota de x")
    e2 = Entity(type="IP", value="1.2.3.4")  # sin nota
    main_window.model.add_entity(e1)
    main_window.model.add_entity(e2)
    main_window.scene.add_entity_visual(e1)
    main_window.scene.add_entity_visual(e2)

    main_window.show_entity_details(e1)
    assert main_window.notes_box.toPlainText() == "nota de x"

    main_window.show_entity_details(e2)
    assert main_window.notes_box.toPlainText() == ""

    main_window.show_entity_details(e1)
    assert main_window.notes_box.toPlainText() == "nota de x"


def test_save_note_writes_to_the_selected_entity(main_window):
    e = Entity(type="Domain", value="x.com")
    main_window.model.add_entity(e)
    main_window.scene.add_entity_visual(e)

    main_window.show_entity_details(e)
    main_window.notes_box.setPlainText("Confirmado: es del cliente real")
    main_window.save_note()

    assert e.user_note == "Confirmado: es del cliente real"


def test_save_note_without_selection_does_not_crash(main_window):
    main_window.notes_box.setPlainText("esto no debería ir a ningún sitio")
    main_window.save_note()  # no debe lanzar excepción
    assert main_window._selected_entity_id is None


def test_html_report_includes_note_when_present(tmp_path):
    model = GraphModel()
    e = Entity(type="Domain", value="x.com", user_note="Confirmado a mano: dominio legítimo")
    model.add_entity(e)
    path = str(tmp_path / "informe.html")
    generate_html_report(model, path)

    content = open(path, encoding="utf-8").read()
    assert "Confirmado a mano" in content
    assert 'class="user-note"' in content


def test_html_report_omits_note_div_when_absent(tmp_path):
    model = GraphModel()
    e = Entity(type="Domain", value="sinnota.com")  # sin nota
    model.add_entity(e)
    path = str(tmp_path / "informe.html")
    generate_html_report(model, path)

    content = open(path, encoding="utf-8").read()
    assert 'class="user-note"' not in content  # la definición CSS no cuenta, solo el div real
    assert "None" not in content


def test_pdf_report_includes_note_text(tmp_path):
    from pypdf import PdfReader
    model = GraphModel()
    e = Entity(type="Domain", value="x.com", user_note="Nota de prueba en el PDF")
    model.add_entity(e)
    path = str(tmp_path / "informe.pdf")
    generate_pdf_report(model, path)

    text = PdfReader(path).pages[0].extract_text()
    assert "Nota de prueba en el PDF" in text
