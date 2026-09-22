"""
Tests de `transforms/gdelt_news_transforms.py`: búsqueda de noticias
compartida entre Organization y Person, generación de entidades URL a
partir de los artículos encontrados, y el manejo defensivo del caso
documentado en el que GDELT devuelve texto plano en vez de JSON válido.
"""
from unittest.mock import MagicMock
import pytest
from core.entity_types import Entity
from transforms.gdelt_news_transforms import OrganizationToNews, PersonToNews


def _mock_ok(articles):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"articles": articles}
    resp.raise_for_status = lambda: None
    return resp


_ARTICULOS_REALES = [
    {"url": "https://reuters.com/tech/apple-news", "url_mobile": "https://reuters.com/tech/apple-news?amp",
     "title": "Apple anuncia nuevos resultados", "seendate": "20260910T120000Z",
     "socialimage": "https://reuters.com/img.jpg", "domain": "reuters.com",
     "language": "English", "sourcecountry": "United States"},
    {"url": "https://bbc.com/news/apple", "title": "Apple lanza producto",
     "seendate": "20260909T080000Z", "domain": "bbc.com",
     "language": "English", "sourcecountry": "United Kingdom"},
]


def test_organization_search_uses_quoted_name_and_recent_timespan(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _mock_ok(_ARTICULOS_REALES)

    monkeypatch.setattr("transforms.gdelt_news_transforms.requests.get", fake_get)
    e = Entity(type="Organization", value="Apple")
    results = OrganizationToNews().run(e)

    assert captured["params"]["query"] == '"Apple"'
    assert captured["params"]["mode"] == "artlist"
    assert captured["params"]["timespan"] == "1m"
    assert len(results) == 2
    assert all(r[0].type == "URL" for r in results)
    assert e.properties["gdelt_total_noticias"] == 2
    assert "Apple anuncia nuevos resultados" in e.properties["gdelt_noticias"]


def test_person_search_shares_same_logic(monkeypatch):
    monkeypatch.setattr(
        "transforms.gdelt_news_transforms.requests.get",
        lambda *a, **k: _mock_ok(_ARTICULOS_REALES),
    )
    e = Entity(type="Person", value="Alguien Famoso")
    results = PersonToNews().run(e)
    assert len(results) == 2
    assert e.properties["gdelt_total_noticias"] == 2


def test_no_results_gives_honest_property_not_an_error(monkeypatch):
    monkeypatch.setattr(
        "transforms.gdelt_news_transforms.requests.get",
        lambda *a, **k: _mock_ok([]),
    )
    e = Entity(type="Organization", value="Empresa Muy Desconocida SL")
    results = OrganizationToNews().run(e)

    assert results == []
    assert e.properties["gdelt_noticias"] == "sin menciones recientes encontradas (último mes)"


def test_non_json_response_raises_honest_error_not_crash(monkeypatch):
    """Documentado por el propio GDELT: ante una consulta rara o un
    problema temporal, puede devolver texto plano (o vacío) con status
    200 en vez de JSON válido -- hay que protegerse explícitamente."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.side_effect = ValueError("no es JSON")
    mock_resp.raise_for_status = lambda: None
    monkeypatch.setattr("transforms.gdelt_news_transforms.requests.get", lambda *a, **k: mock_resp)

    with pytest.raises(RuntimeError, match="no ha devuelto JSON válido"):
        OrganizationToNews().run(Entity(type="Organization", value="X"))


def test_articles_without_url_are_skipped_but_summarized(monkeypatch):
    """Un artículo sin URL no debe crashear ni perderse del resumen de
    texto -- solo se salta a la hora de generar la entidad URL."""
    articulos_con_uno_sin_url = _ARTICULOS_REALES + [
        {"title": "Sin URL", "domain": "x.com", "seendate": "20260911T000000Z"}
    ]
    monkeypatch.setattr(
        "transforms.gdelt_news_transforms.requests.get",
        lambda *a, **k: _mock_ok(articulos_con_uno_sin_url),
    )
    e = Entity(type="Organization", value="Apple")
    results = OrganizationToNews().run(e)

    assert e.properties["gdelt_total_noticias"] == 3
    assert "Sin URL" in e.properties["gdelt_noticias"]
    assert len(results) == 2  # solo se generan entidades para los 2 que sí tienen URL


def test_both_registered_in_transform_registry():
    from transforms import TRANSFORM_REGISTRY
    nombres = [type(t).__name__ for t in TRANSFORM_REGISTRY]
    assert "OrganizationToNews" in nombres
    assert "PersonToNews" in nombres
