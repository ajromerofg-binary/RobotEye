"""
Tests de `transforms/courtlistener_litigation_transforms.py`: búsqueda
por nombre exacto de caso (caseName), compartida entre Organization y
Person, sin generar entidades nuevas (enriquecimiento puro).
"""
from unittest.mock import MagicMock
from core.entity_types import Entity
from transforms.courtlistener_litigation_transforms import (
    OrganizationToLitigation, PersonToLitigation,
)


def _mock_ok(count, results):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"count": count, "results": results}
    resp.raise_for_status = lambda: None
    return resp


_CASOS_REALES = [
    {"absolute_url": "/docket/12345/smith-v-acme-corp/", "caseName": "Smith v. Acme Corp",
     "court": "N.D. Cal.", "dateFiled": "2025-03-14", "docketNumber": "3:25-cv-01234",
     "suitNature": "Contract"},
    {"absolute_url": "/docket/67890/acme-corp-v-jones/", "caseName": "Acme Corp v. Jones",
     "court": "D. Del.", "dateFiled": "2024-11-02", "docketNumber": "1:24-cv-05678"},
]


def test_organization_search_uses_exact_case_name_query(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _mock_ok(23, _CASOS_REALES)

    monkeypatch.setattr(
        "transforms.courtlistener_litigation_transforms.requests.get", fake_get
    )
    e = Entity(type="Organization", value="Acme Corp")
    results = OrganizationToLitigation().run(e)

    assert captured["params"]["q"] == 'caseName:"Acme Corp"'
    assert captured["params"]["type"] == "d"
    assert results == []  # enriquecimiento puro, no genera nodos nuevos
    assert e.properties["courtlistener_total_litigios"] == 23
    assert "Smith v. Acme Corp" in e.properties["courtlistener_litigios"]
    assert "Contract" in e.properties["courtlistener_litigios"]


def test_case_without_suit_nature_has_no_dangling_separator(monkeypatch):
    monkeypatch.setattr(
        "transforms.courtlistener_litigation_transforms.requests.get",
        lambda *a, **k: _mock_ok(23, _CASOS_REALES),
    )
    e = Entity(type="Organization", value="Acme Corp")
    OrganizationToLitigation().run(e)

    assert "Acme Corp v. Jones [D. Del., 2024-11-02]" in e.properties["courtlistener_litigios"]


def test_person_search_shares_same_logic(monkeypatch):
    monkeypatch.setattr(
        "transforms.courtlistener_litigation_transforms.requests.get",
        lambda *a, **k: _mock_ok(3, [{"caseName": "Doe v. Smith", "court": "S.D.N.Y.", "dateFiled": "2023-06-01"}]),
    )
    e = Entity(type="Person", value="John Smith")
    results = PersonToLitigation().run(e)

    assert results == []
    assert e.properties["courtlistener_total_litigios"] == 3


def test_no_results_gives_honest_property_not_an_error(monkeypatch):
    monkeypatch.setattr(
        "transforms.courtlistener_litigation_transforms.requests.get",
        lambda *a, **k: _mock_ok(0, []),
    )
    e = Entity(type="Organization", value="Panadería García SL")
    results = OrganizationToLitigation().run(e)

    assert results == []
    assert "sin expedientes federales" in e.properties["courtlistener_litigios"]
    assert "courtlistener_aviso" not in e.properties  # el aviso solo aparece si hay resultados que matizar


def test_coverage_warning_present_when_results_found(monkeypatch):
    monkeypatch.setattr(
        "transforms.courtlistener_litigation_transforms.requests.get",
        lambda *a, **k: _mock_ok(23, _CASOS_REALES),
    )
    e = Entity(type="Organization", value="Acme Corp")
    OrganizationToLitigation().run(e)

    assert "Solo tribunales federales" in e.properties["courtlistener_aviso"]


def test_both_registered_in_transform_registry():
    from transforms import TRANSFORM_REGISTRY
    nombres = [type(t).__name__ for t in TRANSFORM_REGISTRY]
    assert "OrganizationToLitigation" in nombres
    assert "PersonToLitigation" in nombres
