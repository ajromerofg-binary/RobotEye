"""
Tests de `core/report_generator.py`: construcción de datos del informe,
y generación real de HTML y PDF (verificados con contenido extraído, no
solo "no lanza excepción").
"""
from core.graph_model import GraphModel
from core.entity_types import Entity
from core.report_generator import build_report_data, generate_html_report, generate_pdf_report


def _sample_model():
    model = GraphModel()
    domain = Entity(type="Domain", value="acmecorp.com", properties={"whois_registrar": "GoDaddy"})
    ip = Entity(type="IP", value="8.8.8.8", properties={"pais": "US"})
    email = Entity(type="Email", value="contacto@acmecorp.com")
    for e in (domain, ip, email):
        model.add_entity(e)
    model.add_relation(domain.id, ip.id, "resuelve a (A)")
    model.add_relation(domain.id, email.id, "email encontrado en búsqueda")
    return model


def test_build_report_data_counts_and_relations():
    data = build_report_data(_sample_model())
    assert data["total_nodes"] == 3
    assert data["total_edges"] == 2
    assert data["counts_by_type"] == {"Domain": 1, "Email": 1, "IP": 1}

    domain_entry = next(e for e in data["entities"] if e["type"] == "Domain")
    assert len(domain_entry["relations"]) == 2
    assert domain_entry["properties"]["whois_registrar"] == "GoDaddy"


def test_build_report_data_empty_graph():
    data = build_report_data(GraphModel())
    assert data["total_nodes"] == 0
    assert data["total_edges"] == 0
    assert data["entities"] == []


def test_html_report_contains_expected_data(tmp_path):
    path = tmp_path / "informe.html"
    generate_html_report(_sample_model(), str(path))
    content = path.read_text(encoding="utf-8")
    assert "acmecorp.com" in content
    assert "GoDaddy" in content
    assert "resuelve a (A)" in content
    assert content.startswith("<!DOCTYPE html>")


def test_html_report_escapes_dangerous_characters(tmp_path):
    model = GraphModel()
    e = Entity(
        type="Dork",
        value='site:x.com "<script>alert(1)</script>" & "comillas"',
        properties={"nota": "a < b & c > d"},
    )
    model.add_entity(e)
    path = tmp_path / "informe.html"
    generate_html_report(model, str(path))
    content = path.read_text(encoding="utf-8")
    assert "<script>" not in content
    assert "&lt;script&gt;" in content


def test_html_report_empty_graph_does_not_crash(tmp_path):
    path = tmp_path / "vacio.html"
    generate_html_report(GraphModel(), str(path))
    assert path.exists()


def test_pdf_report_contains_expected_data(tmp_path):
    from pypdf import PdfReader
    path = tmp_path / "informe.pdf"
    generate_pdf_report(_sample_model(), str(path))

    reader = PdfReader(str(path))
    assert len(reader.pages) >= 1
    text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "acmecorp.com" in text
    assert "GoDaddy" in text


def test_pdf_report_empty_graph_does_not_crash(tmp_path):
    path = tmp_path / "vacio.pdf"
    generate_pdf_report(GraphModel(), str(path))
    assert path.exists()


def test_export_actions_exist_on_main_window(main_window):
    assert hasattr(main_window, "export_html_report")
    assert hasattr(main_window, "export_pdf_report")


def test_load_sqlite_still_works_end_to_end(main_window, tmp_path):
    """Regresión del propio desarrollo de esta funcionalidad: un editado
    accidental dejó `load_sqlite` con el cuerpo vacío durante un momento
    -- este test asegura que una recarga real reconstruye modelo Y escena."""
    from unittest.mock import patch

    domain = Entity(type="Domain", value="x.com")
    main_window.model.add_entity(domain)
    main_window.scene.add_entity_visual(domain)
    db_path = str(tmp_path / "p.db")
    main_window.model.save_sqlite(db_path)

    from ui.main_window import MainWindow
    fresh_window = MainWindow()
    with patch("ui.main_window.QFileDialog.getOpenFileName", return_value=(db_path, "")):
        fresh_window.load_sqlite()

    assert len(fresh_window.model.all_entities()) == 1
    assert len(fresh_window.scene.node_items) == 1
