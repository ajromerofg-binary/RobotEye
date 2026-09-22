"""
Tests de `core/email_analyzer.py`: análisis de correos sospechosos
(.eml), incluida la detección honesta de spoofing -- con especial
atención a los DOS falsos positivos reales encontrados durante el
desarrollo antes de dar la heurística por buena.
"""
import datetime
from email.message import EmailMessage as StdEmailMessage
from core.email_analyzer import analyze_eml, populate_graph_from_analysis


def _write_eml(path, **headers_and_body):
    msg = StdEmailMessage()
    for key, value in headers_and_body.get("headers", {}).items():
        if isinstance(value, list):
            for v in value:
                msg[key] = v
        else:
            msg[key] = value
    msg.set_content(headers_and_body.get("body", ""))
    for att in headers_and_body.get("attachments", []):
        msg.add_attachment(att["content"], maintype="application", subtype="octet-stream", filename=att["filename"])
    with open(path, "wb") as f:
        f.write(bytes(msg))
    return path


def test_phishing_email_full_extraction(tmp_path):
    path = _write_eml(
        str(tmp_path / "phishing.eml"),
        headers={
            "From": '"Banco Ejemplo - Seguridad" <soporte@banco-ejemplo.com>',
            "To": "victima@empresa-objetivo.com",
            "Reply-To": "atencion@dominio-sospechoso.ru",
            "Subject": "Urgente: verifique su cuenta",
            "Date": datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "Authentication-Results": "mx.x; spf=fail smtp.mailfrom=banco-ejemplo.com; dkim=none; dmarc=fail",
            # Orden importante: en un .eml real, cada salto ANTEPONE su
            # propia cabecera Received al principio del fichero -- así que
            # la más antigua (más cercana al origen real) queda ÚLTIMA en
            # el fichero. El helper _write_eml asigna en el orden de esta
            # lista, así que aquí van [más reciente, ..., más antigua].
            "Received": [
                "from mx.empresa-objetivo.com by localhost; Tue, 01 Sep 2026 10:00:00 +0000",
                "from smtp-relay.dominio-sospechoso.ru (unknown [203.0.113.45]) by mx.x; Tue, 01 Sep 2026 09:59:50 +0000",
            ],
        },
        body="Verifique su cuenta en http://banco-ejemplo-verificacion.ru/login urgentemente.",
    )
    r = analyze_eml(path)

    assert r["from_address"] == "soporte@banco-ejemplo.com"
    assert r["from_domain"] == "banco-ejemplo.com"
    assert r["to_addresses"] == ["victima@empresa-objetivo.com"]
    assert r["reply_to_address"] == "atencion@dominio-sospechoso.ru"
    assert r["spf"] == "fail"
    assert r["dmarc"] == "fail"
    assert r["origin_ip"] == "203.0.113.45"
    assert r["urls_in_body"] == ["http://banco-ejemplo-verificacion.ru/login"]
    assert len(r["spoofing_indicators"]) == 3  # Reply-To, SPF, DMARC


def test_display_name_with_extra_words_is_not_a_false_positive(tmp_path):
    """Falso positivo real encontrado: un nombre mostrado con palabras
    añadidas ('Banco Ejemplo - Seguridad') SÍ guarda relación real con su
    dominio ('banco-ejemplo.com') -- no debe generar ninguna alerta por
    ese motivo (ya no existe esa heurística, pero el test deja constancia
    de por qué se quitó)."""
    path = _write_eml(
        str(tmp_path / "legit_extra_words.eml"),
        headers={
            "From": '"Banco Ejemplo - Seguridad" <soporte@banco-ejemplo.com>',
            "To": "cliente@x.com",
            "Subject": "Aviso",
            "Date": datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000"),
        },
        body="Aviso rutinario.",
    )
    r = analyze_eml(path)
    assert r["spoofing_indicators"] == []


def test_person_name_not_matching_company_domain_is_not_flagged(tmp_path):
    """Falso positivo real, más grave: el nombre de una PERSONA (Ana
    Lopez) no tiene por qué guardar ninguna relación con el dominio de su
    propia empresa (empresa-real.com) -- es el patrón normal y
    mayoritario, no debe generar ninguna alerta."""
    path = _write_eml(
        str(tmp_path / "legit_person.eml"),
        headers={
            "From": '"Ana Lopez" <ana.lopez@empresa-real.com>',
            "To": "companero@empresa-real.com",
            "Subject": "Informe mensual",
            "Date": datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "Authentication-Results": "mx.x; spf=pass smtp.mailfrom=empresa-real.com; dkim=pass; dmarc=pass",
        },
        body="Adjunto el informe.",
        attachments=[{"filename": "informe.pdf", "content": b"contenido simulado"}],
    )
    r = analyze_eml(path)
    assert r["spoofing_indicators"] == []
    assert r["spf"] == "pass"
    assert len(r["attachments"]) == 1
    assert r["attachments"][0]["filename"] == "informe.pdf"
    assert len(r["attachments"][0]["sha256"]) == 64  # SHA-256 en hexadecimal


def test_email_without_optional_headers_does_not_crash(tmp_path):
    """Un .eml mínimo, sin Reply-To/Authentication-Results/Received, debe
    analizarse sin lanzar ninguna excepción -- muchos clientes de correo
    no incluyen todas las cabeceras opcionales."""
    path = _write_eml(
        str(tmp_path / "minimo.eml"),
        headers={"From": "a@x.com", "To": "b@x.com", "Subject": "Hola"},
        body="Sin nada especial.",
    )
    r = analyze_eml(path)
    assert r["spf"] is None
    assert r["origin_ip"] is None
    assert r["spoofing_indicators"] == []


def test_populate_graph_creates_expected_entities_and_relations(main_window, tmp_path):
    path = _write_eml(
        str(tmp_path / "phishing.eml"),
        headers={
            "From": '"Banco Ejemplo" <soporte@banco-ejemplo.com>',
            "To": "victima@empresa.com",
            "Reply-To": "atencion@sospechoso.ru",
            "Subject": "Alerta",
            "Date": datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "Received": "from x (unknown [203.0.113.45]) by y; Tue, 01 Sep 2026 09:59:50 +0000",
        },
        body="Enlace: http://malicioso.example/a",
    )
    analysis = analyze_eml(path)
    email_msg = populate_graph_from_analysis(main_window.model, main_window.scene, analysis)

    tipos = {e.type for e in main_window.model.all_entities()}
    assert tipos == {"EmailMessage", "Email", "Domain", "IP", "URL"}
    assert len(main_window.model.all_entities()) == len(main_window.scene.node_items)

    vecinos = main_window.model.neighbors(email_msg.id)
    assert len(vecinos) == len(main_window.model.edges())  # todas las relaciones parten del EmailMessage


def test_populate_graph_dedupes_against_existing_entities(main_window, tmp_path):
    """Si el dominio del remitente ya existía en el grafo (investigado
    antes), analizar el correo no debe duplicarlo -- debe conectarse al
    nodo ya existente."""
    from core.entity_types import Entity
    existing_domain = Entity(type="Domain", value="banco-ejemplo.com")
    main_window.model.add_entity(existing_domain)
    main_window.scene.add_entity_visual(existing_domain)

    path = _write_eml(
        str(tmp_path / "phishing.eml"),
        headers={"From": "soporte@banco-ejemplo.com", "To": "v@x.com", "Subject": "X",
                 "Date": datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")},
        body="",
    )
    analysis = analyze_eml(path)
    populate_graph_from_analysis(main_window.model, main_window.scene, analysis)

    dominios = [e for e in main_window.model.all_entities() if e.type == "Domain"]
    assert len(dominios) == 1  # no duplicado
    assert dominios[0].id == existing_domain.id


def test_import_eml_action_exists_on_main_window(main_window):
    assert hasattr(main_window, "import_eml_dialog")
