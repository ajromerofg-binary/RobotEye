"""
Tests de las transforms que no dependen de red -- no tienen excusa para
fallar con una entrada válida, así que se prueban con baterías amplias de
casos reales, incluidos los casos límite que revelaron bugs reales
durante el desarrollo (nombres cortos como "H&M", nombres con tildes,
URLs con formato inusual...).
"""
import hashlib
import pytest
from core.entity_types import Entity

from transforms.phone_transforms import PhoneAnalysis
from transforms.hash_transforms import HashIdentifyType
from transforms.username_gen_transforms import PersonToUsernameGuesses
from transforms.dorking_transforms import DomainToGoogleDorks
from transforms.organization_transforms import (
    OrganizationToPersonDorks,
    OrganizationToUsernameGuesses,
)
from transforms.email_pivot_transforms import EmailToDomain, EmailToPersonGuess
from transforms.url_transforms import URLToDomain
from transforms.breach_paste_transforms import BreachToOriginDomain, PasteToLink
from transforms.email_enrichment_transforms import EmailToUsernameGuess
from transforms.darkweb_transforms import (
    DomainToDarkWebSearch,
    OrganizationToDarkWebSearch,
    EmailToDarkWebSearch,
)


def _assert_valid_results(results):
    assert isinstance(results, list)
    for item in results:
        assert isinstance(item, tuple) and len(item) == 2
        entity, label = item
        assert isinstance(entity, Entity)
        assert isinstance(label, str)


# ---------------------------------------------------------------- Phone --

@pytest.mark.parametrize("numero", [
    "+34611222333", "+34976123456", "+14155552671", "+33612345678",
    "+4915123456789", "+8613800138000",
])
def test_phone_analysis_real_numbers(numero):
    e = Entity(type="Phone", value=numero)
    results = PhoneAnalysis().run(e)
    _assert_valid_results(results)
    assert "pais_region" in e.properties


def test_phone_analysis_invalid_number_raises_clear_error():
    with pytest.raises(RuntimeError):
        PhoneAnalysis().run(Entity(type="Phone", value="+861391234567"))  # rango no asignado


# ----------------------------------------------------------------- Hash --

@pytest.mark.parametrize("hasher", [hashlib.md5, hashlib.sha1, hashlib.sha256, hashlib.sha512])
def test_hash_identify_type_common_algorithms(hasher):
    digest = hasher(b"test123").hexdigest()
    results = HashIdentifyType().run(Entity(type="Hash", value=digest))
    _assert_valid_results(results)


# --------------------------------------------------------- Person/Org --

@pytest.mark.parametrize("nombre", [
    "Ana Lopez", "José García", "Al Pacino", "Björk Guðmundsdóttir",
    "Jean-Paul Sartre", "O'Brien Smith",
])
def test_person_username_guesses_never_crashes(nombre):
    results = PersonToUsernameGuesses().run(Entity(type="Person", value=nombre))
    _assert_valid_results(results)


@pytest.mark.parametrize("nombre,debe_tener_resultado", [
    ("Acme Corp SL", True),
    ("H&M", True),  # bug histórico: daba CERO candidatos antes del fix
    ("Telefónica España", True),  # bug histórico: candidatos con tildes/eñes inválidas
    ("Sr.Robot Labs", True),
    ("3M", True),
])
def test_organization_username_guesses_no_empty_results_regression(nombre, debe_tener_resultado):
    results = OrganizationToUsernameGuesses().run(Entity(type="Organization", value=nombre))
    if debe_tener_resultado:
        assert len(results) > 0, f"'{nombre}' no debería dar cero candidatos (regresión histórica)"
    for entity, _ in results:
        assert entity.value.isascii(), f"'{entity.value}' contiene caracteres no-ASCII (regresión histórica)"


def test_organization_person_dorks_always_generates_five():
    results = OrganizationToPersonDorks().run(Entity(type="Organization", value="Acme Corp"))
    assert len(results) == 5
    _assert_valid_results(results)


# --------------------------------------------------------------- Email --

def test_email_to_domain_extracts_correctly():
    results = EmailToDomain().run(Entity(type="Email", value="juan@acme.com"))
    assert len(results) == 1
    assert results[0][0].value == "acme.com"


@pytest.mark.parametrize("email,esperado", [
    ("juan.perez@x.com", "Juan Perez"),
    ("maria_lopez@x.com", "Maria Lopez"),
])
def test_email_to_person_guess_name_pattern(email, esperado):
    results = EmailToPersonGuess().run(Entity(type="Email", value=email))
    assert len(results) == 1
    assert results[0][0].value == esperado


@pytest.mark.parametrize("email", ["info@x.com", "noreply@x.com", "soporte@x.com"])
def test_email_to_person_guess_generic_mailbox_gives_nothing(email):
    """No debe inventarse un nombre de persona a partir de un buzón genérico."""
    results = EmailToPersonGuess().run(Entity(type="Email", value=email))
    assert results == []


@pytest.mark.parametrize("email", ["info@acme.com", "noreply@x.com"])
def test_email_username_guess_rejects_generic_mailboxes(email):
    with pytest.raises(RuntimeError):
        EmailToUsernameGuess().run(Entity(type="Email", value=email))


# ----------------------------------------------------------------- URL --

@pytest.mark.parametrize("url,esperado", [
    ("https://x.com/a", "x.com"),
    ("https://X.COM/MAYUS", "x.com"),
    ("https://user:pass@x.com:8443/a", "x.com"),  # bug histórico: daba "user"
    ("https://www.user:pass@sub.x.com:443/", "sub.x.com"),
])
def test_url_to_domain_handles_credentials_and_ports(url, esperado):
    results = URLToDomain().run(Entity(type="URL", value=url))
    assert results[0][0].value == esperado


def test_url_to_domain_invalid_url_raises():
    with pytest.raises(RuntimeError):
        URLToDomain().run(Entity(type="URL", value="esto-no-es-una-url"))


# ----------------------------------------------------- Domain (local) --

def test_domain_to_google_dorks_generates_twelve():
    results = DomainToGoogleDorks().run(Entity(type="Domain", value="ejemplo.com"))
    assert len(results) == 12
    _assert_valid_results(results)


# ------------------------------------------------------- Breach/Paste --

def test_breach_to_origin_domain_uses_existing_property():
    e = Entity(type="Breach", value="Adobe", properties={"dominio_origen": "adobe.com"})
    results = BreachToOriginDomain().run(e)
    assert len(results) == 1
    assert results[0][0].value == "adobe.com"


def test_breach_to_origin_domain_no_property_gives_nothing():
    e = Entity(type="Breach", value="X", properties={})
    assert BreachToOriginDomain().run(e) == []


def test_paste_to_link_finds_url_in_properties():
    e = Entity(type="Paste", value="X", properties={"raw_url": "https://pastebin.com/raw/abc"})
    results = PasteToLink().run(e)
    assert len(results) == 1


# -------------------------------------------------------- Dark web link --

@pytest.mark.parametrize("transform_cls,entity_type,value", [
    (DomainToDarkWebSearch, "Domain", "ejemplo.com"),
    (OrganizationToDarkWebSearch, "Organization", "Acme Corp"),
    (EmailToDarkWebSearch, "Email", "ana@ejemplo.com"),
])
def test_darkweb_link_never_makes_network_request(transform_cls, entity_type, value, monkeypatch):
    """El punto más importante de estas 3 transforms: NUNCA deben hacer
    una petición de red (Ahmia prohíbe el scraping en su robots.txt).
    Se parchea requests.get/post/head a nivel global para comprobarlo."""
    import requests

    def _fail(*a, **k):
        raise AssertionError("¡Se ha hecho una petición de red que no debía producirse!")

    monkeypatch.setattr(requests, "get", _fail)
    monkeypatch.setattr(requests, "post", _fail)
    monkeypatch.setattr(requests, "head", _fail)

    e = Entity(type=entity_type, value=value)
    results = transform_cls().run(e)
    assert results == []
    assert "busqueda_dark_web_ahmia" in e.properties
    assert e.properties["busqueda_dark_web_ahmia"].startswith("https://ahmia.fi/search/?q=")
