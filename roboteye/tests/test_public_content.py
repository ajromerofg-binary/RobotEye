"""
Tests de `transforms/public_content_transforms.py`: ejecución automática
de búsquedas de documentos (PDF/XLSX/DOCX) y publicaciones públicas, en
vez de tener que copiar y lanzar el dork a mano.
"""
from unittest.mock import MagicMock
import pytest
from core.entity_types import Entity
from transforms.public_content_transforms import (
    DomainToDocumentSearch, OrganizationToDocumentSearch, OrganizationToPublicPosts,
)

_SAMPLE_HTML = (
    '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Facmecorp.com%2Finforme.pdf">Informe</a>'
    '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Facmecorp.com%2Fdatos.xlsx">Datos</a>'
)


def _mock_ok(text):
    resp = MagicMock(status_code=200, text=text)
    resp.raise_for_status = lambda: None
    return resp


def test_domain_document_search_query_and_results(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["query"] = params["q"]
        return _mock_ok(_SAMPLE_HTML)

    monkeypatch.setattr("transforms.public_content_transforms.requests.get", fake_get)
    results = DomainToDocumentSearch().run(Entity(type="Domain", value="acmecorp.com"))

    assert captured["query"] == "site:acmecorp.com (filetype:pdf OR filetype:xlsx OR filetype:docx)"
    assert len(results) == 2
    assert all(e.type == "URL" for e, _ in results)
    assert {e.value for e, _ in results} == {"https://acmecorp.com/informe.pdf", "https://acmecorp.com/datos.xlsx"}


def test_organization_document_search_query_has_no_site_restriction(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["query"] = params["q"]
        return _mock_ok(_SAMPLE_HTML)

    monkeypatch.setattr("transforms.public_content_transforms.requests.get", fake_get)
    OrganizationToDocumentSearch().run(Entity(type="Organization", value="Acme Corp"))

    assert captured["query"] == '"Acme Corp" (filetype:pdf OR filetype:xlsx OR filetype:docx)'


def test_organization_public_posts_query_covers_linkedin_x_reddit(monkeypatch):
    captured = {}
    sample = '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.linkedin.com%2Fposts%2Facme">Post</a>'

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["query"] = params["q"]
        return _mock_ok(sample)

    monkeypatch.setattr("transforms.public_content_transforms.requests.get", fake_get)
    results = OrganizationToPublicPosts().run(Entity(type="Organization", value="Acme Corp"))

    for site in ("linkedin.com/posts", "x.com", "twitter.com", "reddit.com"):
        assert f"site:{site}" in captured["query"]
    assert len(results) == 1
    assert results[0][0].type == "URL"


@pytest.mark.parametrize("transform_cls,entity_type,value", [
    (DomainToDocumentSearch, "Domain", "x.com"),
    (OrganizationToDocumentSearch, "Organization", "Acme"),
    (OrganizationToPublicPosts, "Organization", "Acme"),
])
def test_no_results_gives_honest_error(transform_cls, entity_type, value, monkeypatch):
    monkeypatch.setattr(
        "transforms.public_content_transforms.requests.get",
        lambda *a, **k: _mock_ok("<html>sin resultados</html>"),
    )
    with pytest.raises(RuntimeError):
        transform_cls().run(Entity(type=entity_type, value=value))


@pytest.mark.parametrize("transform_cls,entity_type,value", [
    (DomainToDocumentSearch, "Domain", "x.com"),
    (OrganizationToDocumentSearch, "Organization", "Acme"),
    (OrganizationToPublicPosts, "Organization", "Acme"),
])
def test_detects_ddg_block(transform_cls, entity_type, value, monkeypatch):
    monkeypatch.setattr(
        "transforms.public_content_transforms.requests.get",
        lambda *a, **k: _mock_ok("<html>DDG.deep.anomalyDetectionBlock({...})</html>"),
    )
    with pytest.raises(RuntimeError, match="bloqueado temporalmente"):
        transform_cls().run(Entity(type=entity_type, value=value))


def test_all_three_marked_uses_ddg_for_throttling():
    """Deben participar en el escalonado de 'Ejecutar todas' igual que el
    resto de transforms que consultan DuckDuckGo."""
    assert DomainToDocumentSearch.uses_ddg is True
    assert OrganizationToDocumentSearch.uses_ddg is True
    assert OrganizationToPublicPosts.uses_ddg is True


def test_document_search_result_chains_into_existing_metadata_transform(monkeypatch):
    """El punto central de esta funcionalidad: el resultado debe encadenar
    solo con URL -> Metadatos del documento, sin ningún cambio en esa
    transform ya existente."""
    from transforms.metadata_transforms import URLToDocumentMetadata

    monkeypatch.setattr(
        "transforms.public_content_transforms.requests.get",
        lambda *a, **k: _mock_ok(_SAMPLE_HTML),
    )
    results = DomainToDocumentSearch().run(Entity(type="Domain", value="acmecorp.com"))
    pdf_entity = next(e for e, _ in results if e.value.endswith(".pdf"))
    assert URLToDocumentMetadata().applies_to(pdf_entity) is True
