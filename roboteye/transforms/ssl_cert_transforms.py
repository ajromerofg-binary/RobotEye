"""
`Domain/IP → Certificado SSL`: conecta al puerto 443 del objetivo y lee su
certificado TLS directamente -- lo mismo que hace cualquier navegador al
abrir una web con HTTPS, solo que aquí se extraen los datos en vez de
mostrar un candado verde.

El campo más valioso para OSINT es el SAN (Subject Alternative Names): un
certificado moderno declara ahí TODOS los nombres de dominio para los que
es válido, y a veces incluye subdominios que `Domain → Subdominios
(crt.sh)` no capturó -- si el certificado se renovó/rotó después de que
los logs de Certificate Transparency lo indexaran, o si crt.sh tiene algún
hueco de cobertura puntual, esta transform puede encontrar subdominios que
la otra no vio (o viceversa; conviene usar ambas).

*** ZONA GRIS: esta transform SÍ toca el objetivo ***
Es una conexión TCP/TLS directa al servidor del objetivo -- el mismo
criterio que separa `Domain → Tecnologías web` del resto de transforms
pasivas. Declara `requires_consent = True`.

Detalle técnico importante: para poder leer el certificado incluso cuando
es autofirmado o el nombre no coincide (casos habituales y no motivo para
negarse a leerlo, ya que el objetivo es inspeccionar, no validar
confianza), hay que conectar con `verify_mode = ssl.CERT_NONE`. Pero con
`CERT_NONE`, el método de alto nivel `getpeercert()` de Python devuelve un
diccionario VACÍO aunque la conexión y la descarga del certificado
funcionen perfectamente -- se comprobó esto en directo antes de escribir
el resto del código. La solución es pedir el certificado en formato
binario (`getpeercert(binary_form=True)`) y parsearlo a mano con la
librería `cryptography`.
"""
import socket
import ssl
from typing import List, Tuple
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from core.entity_types import Entity
from core.transform_base import Transform, register

CONNECT_TIMEOUT = 10
PORT = 443


@register
class DomainToSSLCertificate(Transform):
    name = "Domain → Certificado SSL"
    description = "Conecta al puerto 443 y lee el certificado TLS -- revela SANs (posibles subdominios), emisor y caducidad. TOCA el objetivo, requiere confirmación."
    input_types = ["Domain", "IP"]
    requires_consent = True

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        host = entity.value
        context = ssl.create_default_context()
        # No verificamos identidad/confianza a propósito -- el objetivo es
        # LEER el certificado (autofirmado o no, caducado o no), no decidir
        # si el navegador debería confiar en él.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        try:
            with socket.create_connection((host, PORT), timeout=CONNECT_TIMEOUT) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert_bin = ssock.getpeercert(binary_form=True)
        except socket.timeout:
            raise RuntimeError(f"Tiempo de espera agotado conectando a {host}:{PORT}.")
        except ConnectionRefusedError:
            raise RuntimeError(f"Conexión rechazada en {host}:{PORT} -- probablemente no hay HTTPS en ese puerto.")
        except ssl.SSLError as ex:
            raise RuntimeError(f"Error TLS al conectar con {host}:{PORT}: {ex}")
        except OSError as ex:
            raise RuntimeError(f"No se pudo conectar a {host}:{PORT}: {ex}")

        if not cert_bin:
            raise RuntimeError(f"{host}:{PORT} no presentó ningún certificado.")

        try:
            cert = x509.load_der_x509_certificate(cert_bin, default_backend())
        except Exception as ex:
            raise RuntimeError(f"El certificado recibido no se pudo interpretar: {ex}")

        entity.properties.update({
            "ssl_emisor": cert.issuer.rfc4514_string(),
            "ssl_sujeto": cert.subject.rfc4514_string(),
            "ssl_valido_desde": str(cert.not_valid_before_utc),
            "ssl_valido_hasta": str(cert.not_valid_after_utc),
            "ssl_numero_serie": str(cert.serial_number),
        })

        sans = []
        try:
            san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            sans = san_ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            pass

        entity.properties["ssl_sans"] = ", ".join(sans) if sans else "sin extensión SAN"

        results = []
        seen = set()
        for name in sans:
            name_clean = name.lower().strip()
            if name_clean.startswith("*."):
                name_clean = name_clean[2:]  # quitar el prefijo de wildcard explícitamente,
                # nunca con .lstrip("*.") -- ese método trata el argumento
                # como un conjunto de caracteres a quitar, no un prefijo
                # literal (bug clásico ya encontrado y documentado en
                # asn_transforms.py durante la auditoría de esta sesión)
            if name_clean and name_clean != host.lower() and name_clean not in seen:
                seen.add(name_clean)
                results.append((Entity(type="Domain", value=name_clean), "nombre alternativo del certificado (SAN)"))
        return results
