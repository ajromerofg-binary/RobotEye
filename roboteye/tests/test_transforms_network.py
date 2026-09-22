"""
Tests de transforms que dependen de red externa. Todas usan mocks --
pero mocks que reproducen fielmente el esquema REAL de cada API,
investigado y documentado en cada módulo (RFC 9083 para RDAP, el formato
de k-anonimato de Pwned Passwords, el formato vCard de RDAP, los códigos
de Spamhaus ZEN...), no datos inventados a ciegas.
"""
from unittest.mock import MagicMock
import pytest
from core.entity_types import Entity


def _assert_valid_results(results):
    assert isinstance(results, list)
    for item in results:
        assert isinstance(item, tuple) and len(item) == 2


# --------------------------------------------------------------- WHOIS --

def test_whois_strips_whitespace_from_fields(monkeypatch):
    """Bug histórico: campos WHOIS sin limpiar de espacios podían crear
    duplicados no detectados (el modelo deduplica por string exacto)."""
    from transforms.whois_transforms import DomainToWhois

    mock_w = MagicMock(org="   Acme con espacios   ", name=None, emails=["  a@x.com  "],
                        registrant_phone=None, phone=None, admin_phone=None, registrant_phone_number=None,
                        registrar="R", creation_date=None, expiration_date=None)
    monkeypatch.setattr("transforms.whois_transforms.pywhois.whois", lambda domain: mock_w)

    e = Entity(type="Domain", value="x.com")
    results = DomainToWhois().run(e)
    for entity, _ in results:
        assert entity.value == entity.value.strip()


def test_whois_missing_fields_do_not_show_literal_none(monkeypatch):
    """Bug histórico: un campo ausente mostraba el literal 'None' en vez
    de un valor legible."""
    from transforms.whois_transforms import DomainToWhois

    mock_w = MagicMock(org=None, name=None, emails=[], registrant_phone=None, phone=None,
                        admin_phone=None, registrant_phone_number=None,
                        registrar=None, creation_date=None, expiration_date=None)
    monkeypatch.setattr("transforms.whois_transforms.pywhois.whois", lambda domain: mock_w)

    e = Entity(type="Domain", value="x.com")
    DomainToWhois().run(e)
    assert "None" not in str(e.properties.values())


# ------------------------------------------------------------- crt.sh --

def test_crtsh_uses_browser_headers_not_old_signature(monkeypatch):
    """Bug histórico: este módulo seguía usando la cabecera antigua
    'MaltegoClone/0.1' (nombre previo del proyecto), sin actualizar tras
    centralizar las cabeceras realistas."""
    from transforms.crtsh_transforms import DomainToSubdomainsCrtSh
    from transforms.dorking_transforms import BROWSER_HEADERS

    captured = {}

    def fake_get(url, timeout=None, headers=None):
        captured["headers"] = headers
        resp = MagicMock(status_code=200)
        resp.json.return_value = [{"name_value": "sub.ejemplo.com"}]
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr("transforms.crtsh_transforms.requests.get", fake_get)
    DomainToSubdomainsCrtSh().run(Entity(type="Domain", value="ejemplo.com"))
    assert captured["headers"] == BROWSER_HEADERS
    assert "MaltegoClone" not in str(captured["headers"])


def test_crtsh_wildcard_and_dedup(monkeypatch):
    from transforms.crtsh_transforms import DomainToSubdomainsCrtSh

    def fake_get(url, timeout=None, headers=None):
        resp = MagicMock(status_code=200)
        resp.json.return_value = [
            {"name_value": "*.ejemplo.com\nwww.ejemplo.com\napi.ejemplo.com"},
            {"name_value": "www.ejemplo.com"},  # duplicado
        ]
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr("transforms.crtsh_transforms.requests.get", fake_get)
    results = DomainToSubdomainsCrtSh().run(Entity(type="Domain", value="ejemplo.com"))
    valores = [e.value for e, _ in results]
    assert valores.count("www.ejemplo.com") == 1
    assert "ejemplo.com" not in valores  # el propio dominio no se incluye a sí mismo
    assert not any(v.startswith("*") for v in valores)


# ------------------------------------------------------------ DDG block --

def test_ddg_block_detector():
    from transforms.dorking_transforms import is_ddg_blocked
    assert is_ddg_blocked("<html>DDG.deep.anomalyDetectionBlock({...})</html>") is True
    assert is_ddg_blocked("Please type the characters you see below") is True
    assert is_ddg_blocked("<a class='result__a'>resultado normal</a>") is False


@pytest.mark.parametrize("transform_import,entity_type,value", [
    ("transforms.dorking_transforms.DorkToResults", "Dork", "site:x.com"),
    ("transforms.organization_transforms.OrganizationToProbableDomain", "Organization", "Acme"),
    ("transforms.email_harvest_transforms.DomainToEmailHarvest", "Domain", "x.com"),
])
def test_ddg_based_transforms_detect_block(transform_import, entity_type, value, monkeypatch):
    module_path, cls_name = transform_import.rsplit(".", 1)
    module = __import__(module_path, fromlist=[cls_name])
    transform_cls = getattr(module, cls_name)

    mock_resp = MagicMock(status_code=200, text="<html>DDG.deep.anomalyDetectionBlock({...})</html>")
    mock_resp.raise_for_status = lambda: None
    monkeypatch.setattr(f"{module_path}.requests.get", lambda *a, **k: mock_resp)

    with pytest.raises(RuntimeError, match="bloqueado temporalmente"):
        transform_cls().run(Entity(type=entity_type, value=value))


# --------------------------------------------------------------- ASN ---

def test_asn_extract_number_handles_all_formats():
    from transforms.asn_transforms import _extract_asn_number
    assert _extract_asn_number("AS15169") == "15169"
    assert _extract_asn_number("ASN13335") == "13335"  # antes daba 'N13335' con .lstrip("AS")
    assert _extract_asn_number("as15169") == "15169"
    assert _extract_asn_number("15169") == "15169"


def test_asn_prefixes_survives_incomplete_entry(monkeypatch):
    """Bug histórico: KeyError si un prefix de RIPEstat venía sin la clave 'prefix'."""
    from transforms.asn_transforms import ASNToPrefixes

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"data": {"prefixes": [{"prefix": "8.8.8.0/24"}, {"timelines": []}]}}
    mock_resp.raise_for_status = lambda: None
    monkeypatch.setattr("transforms.asn_transforms.requests.get", lambda *a, **k: mock_resp)

    e = Entity(type="ASN", value="AS15169")
    ASNToPrefixes().run(e)  # no debe lanzar KeyError
    assert e.properties["total_prefijos"] == 1


# ---------------------------------------------------------------- RDAP --

def test_rdap_extracts_vcard_organization_name(monkeypatch):
    from transforms.ip_enrichment_transforms import IPToRDAP

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "name": "GOOGLE", "country": "US",
        "startAddress": "8.8.8.0", "endAddress": "8.8.8.255", "type": "ALLOCATION",
        "entities": [{"vcardArray": ["vcard", [["fn", {}, "text", "Google LLC"]]]}],
    }
    mock_resp.raise_for_status = lambda: None
    monkeypatch.setattr("transforms.ip_enrichment_transforms.requests.get", lambda *a, **k: mock_resp)

    results = IPToRDAP().run(Entity(type="IP", value="8.8.8.8"))
    assert results[0][0].value == "Google LLC"


def test_ip_blocklist_distinguishes_error_from_real_listing(monkeypatch):
    """Bug potencial evitado a propósito: el rango 127.255.255.* de
    Spamhaus es un código de ERROR de la consulta, no un listado real."""
    from transforms.ip_enrichment_transforms import IPToBlocklist

    monkeypatch.setattr("dns.resolver.resolve", lambda *a, **k: ["127.255.255.254"])
    with pytest.raises(RuntimeError, match="error de consulta"):
        IPToBlocklist().run(Entity(type="IP", value="1.2.3.4"))


def test_ip_blocklist_real_listing_reported_correctly(monkeypatch):
    from transforms.ip_enrichment_transforms import IPToBlocklist

    monkeypatch.setattr("dns.resolver.resolve", lambda *a, **k: ["127.0.0.4"])
    e = Entity(type="IP", value="1.2.3.4")
    IPToBlocklist().run(e)
    assert "XBL" in e.properties["listas_negras"]


# ----------------------------------------------------------------- SSL --

def test_ssl_cve_extraction_v2_vs_v3_baseseverity_location():
    """CVSS v3.x guarda baseSeverity DENTRO de cvssData; v2 lo guarda
    FUERA -- si no se distingue, se rompe la extracción de CVEs antiguos."""
    from transforms.cve_transforms import _extract_cvss

    cve_v31 = {"metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}]}}
    assert _extract_cvss(cve_v31) == (9.8, "3.1")

    cve_v2 = {"metrics": {"cvssMetricV2": [{"cvssData": {"baseScore": 7.5}, "baseSeverity": "HIGH"}]}}
    assert _extract_cvss(cve_v2) == (7.5, "2.0")

    assert _extract_cvss({"metrics": {}}) is None


def test_software_to_cves_rate_limit_handled(monkeypatch):
    from transforms.cve_transforms import SoftwareToCVEs
    mock_resp = MagicMock(status_code=429)
    monkeypatch.setattr("transforms.cve_transforms.requests.get", lambda *a, **k: mock_resp)
    with pytest.raises(RuntimeError, match="exceso de consultas"):
        SoftwareToCVEs().run(Entity(type="Software", value="WordPress"))


# ------------------------------------------------------ Pwned Passwords --

def test_pwned_passwords_k_anonymity_never_sends_full_hash(monkeypatch):
    """El punto más importante de esta transform: el servidor NUNCA debe
    recibir el hash completo, solo los 5 primeros caracteres."""
    import hashlib
    from transforms.hash_pwned_transforms import HashToPwnedPasswords

    full_hash = hashlib.sha1(b"password").hexdigest().upper()
    prefix, suffix = full_hash[:5], full_hash[5:]
    captured_urls = []

    def fake_get(url, headers=None, timeout=None):
        captured_urls.append(url)
        resp = MagicMock(status_code=200, text=f"{suffix}:9545824")
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr("transforms.hash_pwned_transforms.requests.get", fake_get)
    e = Entity(type="Hash", value=full_hash.lower())
    HashToPwnedPasswords().run(e)

    assert len(captured_urls) == 1
    assert captured_urls[0].endswith(prefix)
    assert suffix not in captured_urls[0]  # el hash completo JAMÁS debe salir de la máquina
    assert "9545824" in e.properties["pwned_passwords"]


def test_pwned_passwords_applies_to_only_sha1():
    from transforms.hash_pwned_transforms import HashToPwnedPasswords
    import hashlib
    t = HashToPwnedPasswords()
    assert t.applies_to(Entity(type="Hash", value=hashlib.sha1(b"x").hexdigest())) is True
    assert t.applies_to(Entity(type="Hash", value=hashlib.sha256(b"x").hexdigest())) is False


# --------------------------------------------------------------- Email --

def test_gravatar_uses_sha256_and_normalizes_email(monkeypatch):
    import hashlib
    from transforms.email_enrichment_transforms import EmailToGravatar

    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"entry": [{"displayName": "Ana", "profileUrl": "https://gravatar.com/ana"}]}
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr("transforms.email_enrichment_transforms.requests.get", fake_get)
    EmailToGravatar().run(Entity(type="Email", value="Ana.Lopez@Example.com"))
    expected_hash = hashlib.sha256("ana.lopez@example.com".encode()).hexdigest()
    assert expected_hash in captured["url"]


# --------------------------------------------------------------- Image --

def test_image_exif_extraction_real_gps_roundtrip():
    """Verificación con datos reales, no mockeados: construye una imagen
    JPEG con EXIF+GPS real y comprueba que las coordenadas decimales
    calculadas coinciden con la ubicación real (Torre Eiffel)."""
    import io
    from unittest.mock import patch
    from PIL import Image
    from PIL.TiffImagePlugin import IFDRational
    from transforms.image_metadata_transforms import URLToImageMetadata

    img = Image.new("RGB", (10, 10), color="red")
    exif = img.getexif()
    exif[271] = "Apple"
    exif[272] = "iPhone 14"
    exif[34853] = {
        1: "N", 2: (IFDRational(48, 1), IFDRational(51, 1), IFDRational(2949, 100)),
        3: "E", 4: (IFDRational(2, 1), IFDRational(17, 1), IFDRational(4008, 100)),
    }
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)

    mock_resp = MagicMock(status_code=200, headers={})
    mock_resp.iter_content = lambda chunk_size: [buf.getvalue()]
    mock_resp.raise_for_status = lambda: None

    with patch("transforms.metadata_transforms.requests.get", return_value=mock_resp):
        e = Entity(type="URL", value="https://x.com/foto.jpg")
        URLToImageMetadata().run(e)

    lat, lon = (float(x) for x in e.properties["gps_coordenadas"].split(", "))
    assert abs(lat - 48.858) < 0.01
    assert abs(lon - 2.294) < 0.01


@pytest.mark.parametrize("url,esperado", [
    ("https://x.com/foto.jpg", True),
    ("https://x.com/foto.png", False),
    ("https://x.com/foto.jpg#fragmento", True),  # bug histórico: el fragmento rompía la detección
])
def test_image_metadata_applies_to(url, esperado):
    from transforms.image_metadata_transforms import URLToImageMetadata
    assert URLToImageMetadata().applies_to(Entity(type="URL", value=url)) is esperado


# --------------------------------------------------------------- MAC ---

def test_mac_vendor_lookup(monkeypatch):
    from transforms.mac_vendor_transforms import MACAddressToVendor
    mock_resp = MagicMock(status_code=200, text="Apple, Inc.")
    mock_resp.raise_for_status = lambda: None
    monkeypatch.setattr("transforms.mac_vendor_transforms.requests.get", lambda *a, **k: mock_resp)

    e = Entity(type="MACAddress", value="FC:FB:FB:01:FA:21")
    MACAddressToVendor().run(e)
    assert e.properties["fabricante"] == "Apple, Inc."


def test_mac_vendor_not_found(monkeypatch):
    from transforms.mac_vendor_transforms import MACAddressToVendor
    mock_resp = MagicMock(status_code=404)
    monkeypatch.setattr("transforms.mac_vendor_transforms.requests.get", lambda *a, **k: mock_resp)
    with pytest.raises(RuntimeError):
        MACAddressToVendor().run(Entity(type="MACAddress", value="02:00:00:00:00:00"))


# ---------------------------------------------------------------- SMTP --

def test_smtp_verification_lowercases_domain(monkeypatch):
    """Bug histórico: un artefacto de compresión DNS podía dejar el
    dominio en mayúsculas en el resultado mostrado."""
    from transforms.smtp_verify_transforms import EmailToSMTPVerification

    captured = {}

    def fake_resolve(domain):
        captured["domain"] = domain
        return None  # forzamos el camino de error para no seguir conectando

    monkeypatch.setattr("transforms.smtp_verify_transforms._resolve_mx_host", fake_resolve)
    with pytest.raises(RuntimeError):
        EmailToSMTPVerification().run(Entity(type="Email", value="a@EJEMPLO.COM"))
    assert captured["domain"] == "ejemplo.com"


def test_smtp_null_mx_detected_as_no_mx(monkeypatch):
    """Bug histórico: un registro Null MX (RFC 7505, el propio '.') se
    convertía en cadena vacía en vez de detectarse como 'sin MX'."""
    from transforms.smtp_verify_transforms import _resolve_mx_host

    mock_record = MagicMock(preference=0)
    mock_record.exchange = "."
    monkeypatch.setattr("dns.resolver.resolve", lambda *a, **k: [mock_record])
    assert _resolve_mx_host("example.com") is None
