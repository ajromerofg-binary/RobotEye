"""
Tests de `transforms/sec_edgar_transforms.py`: búsqueda de CIK por
nombre (tres estrategias en cascada), registro oficial, financieros
básicos, y la caché a nivel de módulo del fichero de tickers.
"""
from unittest.mock import MagicMock
import pytest
import transforms.sec_edgar_transforms as mod
from transforms.sec_edgar_transforms import (
    OrganizationToSECRegistry, _find_cik_by_name, _latest_10k_value,
)
from core.entity_types import Entity


@pytest.fixture(autouse=True)
def _reset_ticker_cache():
    """La caché es a nivel de módulo -- se resetea entre tests para que
    no se filtren datos de un mock a otro test."""
    mod._ticker_cache = None
    yield
    mod._ticker_cache = None


def _mock_ok(payload):
    resp = MagicMock(status_code=200)
    resp.json.return_value = payload
    resp.raise_for_status = lambda: None
    return resp


_TICKERS_PAYLOAD = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corporation"},
    "2": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
}


def test_find_cik_exact_match(monkeypatch):
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: _mock_ok(_TICKERS_PAYLOAD))
    assert _find_cik_by_name("Apple Inc.") == "0000320193"


def test_find_cik_starts_with_match(monkeypatch):
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: _mock_ok(_TICKERS_PAYLOAD))
    assert _find_cik_by_name("Microsoft") == "0000789019"


def test_find_cik_substring_match_as_last_resort(monkeypatch):
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: _mock_ok(_TICKERS_PAYLOAD))
    assert _find_cik_by_name("Alphabet") == "0001652044"


def test_find_cik_not_found_returns_none(monkeypatch):
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: _mock_ok(_TICKERS_PAYLOAD))
    assert _find_cik_by_name("Panadería García SL") is None


def test_ticker_map_is_cached_across_calls(monkeypatch):
    calls = []

    def fake_get(*a, **k):
        calls.append(1)
        return _mock_ok(_TICKERS_PAYLOAD)

    monkeypatch.setattr(mod.requests, "get", fake_get)
    _find_cik_by_name("Apple")
    _find_cik_by_name("Microsoft")
    _find_cik_by_name("Alphabet")
    assert len(calls) == 1  # un único fetch para las 3 búsquedas


def test_latest_10k_value_filters_out_quarterly_filings(monkeypatch):
    payload = {
        "units": {"USD": [
            {"end": "2024-09-28", "val": 391035000000, "form": "10-K", "filed": "2024-11-01"},
            {"end": "2023-09-30", "val": 383285000000, "form": "10-K", "filed": "2023-11-02"},
            {"end": "2024-06-29", "val": 85777000000, "form": "10-Q", "filed": "2024-08-01"},
        ]}
    }
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: _mock_ok(payload))
    fecha, valor = _latest_10k_value("0000320193", "Revenues")
    assert fecha == "2024-09-28"
    assert valor == 391035000000


def test_latest_10k_value_returns_none_on_404(monkeypatch):
    resp_404 = MagicMock(status_code=404)
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: resp_404)
    assert _latest_10k_value("0000320193", "NetIncomeLoss") is None


def test_full_run_extracts_registry_and_financials(monkeypatch):
    submissions_payload = {
        "name": "Apple Inc.",
        "sic": "3571",
        "sicDescription": "Electronic Computers",
        "stateOfIncorporation": "CA",
        "tickers": ["AAPL"],
        "exchanges": ["Nasdaq"],
        "formerNames": [{"name": "APPLE COMPUTER INC", "from": "1994-01-01", "to": "2007-01-01"}],
    }
    revenue_payload = {"units": {"USD": [
        {"end": "2024-09-28", "val": 391035000000, "form": "10-K", "filed": "2024-11-01"},
    ]}}
    netincome_resp = MagicMock(status_code=404)

    def fake_get(url, headers=None, timeout=None):
        if "company_tickers.json" in url:
            return _mock_ok(_TICKERS_PAYLOAD)
        if "submissions" in url:
            return _mock_ok(submissions_payload)
        if "Revenues" in url:
            return _mock_ok(revenue_payload)
        if "NetIncomeLoss" in url:
            return netincome_resp
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr(mod.requests, "get", fake_get)

    e = Entity(type="Organization", value="Apple")
    results = OrganizationToSECRegistry().run(e)

    assert results == []
    assert e.properties["sec_razon_social"] == "Apple Inc."
    assert e.properties["sec_cik"] == "320193"  # sin ceros a la izquierda
    assert e.properties["sec_sic"] == "3571 (Electronic Computers)"
    assert e.properties["sec_estado_incorporacion"] == "CA"
    assert e.properties["sec_tickers"] == "AAPL"
    assert e.properties["sec_mercados"] == "Nasdaq"
    assert e.properties["sec_nombres_anteriores"] == "APPLE COMPUTER INC"
    assert "391,035,000,000" in e.properties["sec_ingresos_ultimo_10k"]
    assert "2024-09-28" in e.properties["sec_ingresos_ultimo_10k"]
    assert "sec_beneficio_neto_ultimo_10k" not in e.properties  # 404 -> no se inventa el dato


def test_run_raises_honest_error_when_not_a_us_public_company(monkeypatch):
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: _mock_ok(_TICKERS_PAYLOAD))
    with pytest.raises(RuntimeError, match="no se encontró en el registro de la SEC"):
        OrganizationToSECRegistry().run(Entity(type="Organization", value="Panadería García SL"))


def test_registered_in_transform_registry():
    from transforms import TRANSFORM_REGISTRY
    nombres = [type(t).__name__ for t in TRANSFORM_REGISTRY]
    assert "OrganizationToSECRegistry" in nombres
