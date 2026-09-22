"""
Tests de `transforms/ofac_sanctions_transforms.py`: parseo del CSV crudo
de OFAC (sin cabecera, marcador `-0-` para campos vacíos), búsqueda por
nombre compartida entre Organization y Person, y la caché a nivel de
módulo de la lista SDN completa.
"""
from unittest.mock import MagicMock
import transforms.ofac_sanctions_transforms as mod
from transforms.ofac_sanctions_transforms import (
    OrganizationToOFACSanctions, PersonToOFACSanctions, _get_sdn_list, _clean,
)
from core.entity_types import Entity

# Filas reales tal y como las devuelve treasury.gov/ofac/downloads/sdn.csv
_CSV_REAL = (
    '6823,"PATINO FOMEQUE, Victor Julio","individual","SDNT",-0-,-0-,-0-,-0-,-0-,-0-,-0-,'
    '"DOB 31 Jan 1959; Cedula No. 16473543 (Colombia)."\n'
    '3749,"LA COMPANIA GENERAL DE NIQUEL",-0-,"CUBA",-0-,-0-,-0-,-0-,-0-,-0-,-0-,-0-\n'
)


def _reset_cache_and_mock(monkeypatch, csv_text=_CSV_REAL):
    mod._sdn_cache = None
    resp = MagicMock(status_code=200, text=csv_text)
    resp.raise_for_status = lambda: None
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: resp)


def test_clean_translates_dash_zero_marker_to_empty_string():
    assert _clean("-0-") == ""
    assert _clean("SDNT") == "SDNT"
    assert _clean("  -0-  ") == ""


def test_parses_raw_csv_without_header_correctly(monkeypatch):
    _reset_cache_and_mock(monkeypatch)
    lista = _get_sdn_list()

    assert len(lista) == 2
    assert lista[0]["sdn_name"] == "PATINO FOMEQUE, Victor Julio"
    assert lista[0]["sdn_type"] == "individual"
    assert lista[0]["program"] == "SDNT"
    assert lista[1]["sdn_type"] == "-0-"  # entidad, no persona


def test_person_transform_finds_match_and_cleans_remarks(monkeypatch):
    _reset_cache_and_mock(monkeypatch)
    e = Entity(type="Person", value="PATINO FOMEQUE")
    results = PersonToOFACSanctions().run(e)

    assert results == []
    assert e.properties["ofac_sdn_total_coincidencias"] == 1
    assert "DOB 31 Jan 1959" in e.properties["ofac_sdn_coincidencias"]
    assert "-0-" not in e.properties["ofac_sdn_coincidencias"]  # el marcador nunca se filtra tal cual
    assert "Coincidencia de NOMBRE, no de identidad" in e.properties["ofac_sdn_aviso"]


def test_organization_transform_match_without_dangling_separator(monkeypatch):
    """Cuando remarks está vacío (-0-), el resumen no debe terminar en
    un separador '-- ' colgando sin nada después."""
    _reset_cache_and_mock(monkeypatch)
    e = Entity(type="Organization", value="LA COMPANIA GENERAL DE NIQUEL")
    OrganizationToOFACSanctions().run(e)

    assert "CUBA" in e.properties["ofac_sdn_coincidencias"]
    assert e.properties["ofac_sdn_coincidencias"].endswith("]")


def test_no_match_gives_honest_property_not_an_error(monkeypatch):
    """A diferencia de otras transforms, 'sin coincidencias' aquí NO es
    un error -- es el resultado más común y esperable (la inmensa
    mayoría de organizaciones/personas no están sancionadas)."""
    _reset_cache_and_mock(monkeypatch)
    e = Entity(type="Organization", value="Panadería García SL")
    results = OrganizationToOFACSanctions().run(e)

    assert results == []
    assert e.properties["ofac_sdn"] == "sin coincidencias en la lista SDN de OFAC"


def test_sdn_list_cache_is_shared_across_both_transforms(monkeypatch):
    mod._sdn_cache = None
    resp = MagicMock(status_code=200, text=_CSV_REAL)
    resp.raise_for_status = lambda: None
    calls = []

    def fake_get(*a, **k):
        calls.append(1)
        return resp

    monkeypatch.setattr(mod.requests, "get", fake_get)

    OrganizationToOFACSanctions().run(Entity(type="Organization", value="X"))
    PersonToOFACSanctions().run(Entity(type="Person", value="Y"))
    OrganizationToOFACSanctions().run(Entity(type="Organization", value="Z"))

    assert len(calls) == 1  # un único fetch para las 3 búsquedas, 2 transforms distintas


def test_short_or_malformed_rows_are_skipped_not_crashed(monkeypatch):
    """Una fila corta (menos de 12 campos) no debe crashear el parseo de
    todo el fichero -- se salta esa fila y se sigue con el resto."""
    csv_con_fila_corta = _CSV_REAL + "999,\"INCOMPLETA\"\n"
    _reset_cache_and_mock(monkeypatch, csv_con_fila_corta)
    lista = _get_sdn_list()
    assert len(lista) == 2  # la fila corta se descarta, no se cuela ni crashea


def test_both_registered_in_transform_registry():
    from transforms import TRANSFORM_REGISTRY
    nombres = [type(t).__name__ for t in TRANSFORM_REGISTRY]
    assert "OrganizationToOFACSanctions" in nombres
    assert "PersonToOFACSanctions" in nombres
