"""
Tests del registro de actividad exportable: rastreo estructurado de cada
`MainWindow.log()`, su formateo en texto plano, y la exportación a
fichero (`MainWindow.export_activity_log`).
"""
from unittest.mock import patch


def test_log_appends_structured_entry_with_timestamp_and_message(main_window):
    main_window.log("Entidad añadida: Domain = acmecorp.com")
    assert len(main_window._activity_log) == 1
    entrada = main_window._activity_log[0]
    assert "timestamp" in entrada
    assert entrada["message"] == "Entidad añadida: Domain = acmecorp.com"


def test_log_accumulates_multiple_entries_in_order(main_window):
    main_window.log("primero")
    main_window.log("segundo")
    main_window.log("tercero")
    mensajes = [e["message"] for e in main_window._activity_log]
    assert mensajes == ["primero", "segundo", "tercero"]


def test_format_activity_log_empty_session_gives_honest_message(main_window):
    texto = main_window._format_activity_log()
    assert "sin actividad" in texto


def test_format_activity_log_includes_timestamp_and_message(main_window):
    main_window.log("Correo analizado: 3 indicadores encontrados")
    texto = main_window._format_activity_log()
    assert "Correo analizado: 3 indicadores encontrados" in texto
    assert texto.startswith("[")  # el timestamp entre corchetes va primero


def test_export_activity_log_writes_all_entries_to_file(main_window, tmp_path):
    main_window.log("Entidad añadida: Domain = acmecorp.com")
    main_window.log("Ejecutando 3 transform(s) pasivas...")

    path = str(tmp_path / "registro.txt")
    with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(path, "")):
        main_window.export_activity_log()

    contenido = open(path, encoding="utf-8").read()
    assert "Entidad añadida" in contenido
    assert "Ejecutando 3 transform" in contenido


def test_export_activity_log_cancelled_dialog_does_not_crash(main_window, tmp_path):
    main_window.log("esto no debería exportarse a ningún sitio")
    with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=("", "")):
        main_window.export_activity_log()  # no debe lanzar excepción


def test_export_activity_log_success_message_is_logged_after_export(main_window, tmp_path):
    """El propio mensaje de éxito se registra DESPUÉS de escribir el
    fichero -- no debe aparecer dentro de su propio contenido exportado."""
    main_window.log("evento de prueba")
    path = str(tmp_path / "registro.txt")

    with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(path, "")):
        main_window.export_activity_log()

    contenido = open(path, encoding="utf-8").read()
    assert "exportado en" not in contenido  # el mensaje de éxito no se auto-incluye
    assert any("exportado en" in e["message"] for e in main_window._activity_log)


def test_export_activity_log_records_error_if_write_fails(main_window):
    """Si la escritura falla (ej. ruta inválida), debe quedar constancia
    en el propio registro, no fallar en silencio ni crashear la app."""
    with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=("/ruta/que/no/existe/x.txt", "")):
        main_window.export_activity_log()  # no debe lanzar excepción
    assert any("Error al exportar" in e["message"] for e in main_window._activity_log)
