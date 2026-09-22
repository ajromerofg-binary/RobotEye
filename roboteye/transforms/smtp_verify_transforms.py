"""
*** ZONA GRIS: esta transform SÍ toca el objetivo ***

Verificación de buzón de correo vía protocolo SMTP ("SMTP verify" / "RCPT TO
probing"): conecta directamente al servidor de correo (MX) del dominio del
email y usa el propio protocolo SMTP para preguntarle si ese buzón concreto
existe, SIN enviar ningún correo real -- se corta la conversación justo
antes del paso "DATA" (el que transmitiría contenido).

Por qué vive aparte, igual que webtech_transforms.py: esto no consulta a un
tercero, es una conexión de red directa al servidor de correo del objetivo
-- el mismo criterio que separó `Domain → Tecnologías web` del resto de
transforms pasivas. Declara `requires_consent = True` y la UI exige
confirmación explícita antes de ejecutarla.

Honestidad sobre los límites de esta técnica (importante):
  - Muchos proveedores grandes (Gmail, Outlook/Microsoft 365, la mayoría de
    servicios de email en la nube) devuelven un "250 OK" para CUALQUIER
    buzón que se les pregunte, exista o no, precisamente para impedir este
    tipo de enumeración. Un resultado "existe" en esos proveedores no es
    fiable.
  - El puerto TCP 25 (SMTP) está bloqueado de salida en muchísimas redes
    residenciales, corporativas y de proveedores cloud, precisamente para
    frenar spam y este tipo de sondeo. Si la conexión ni siquiera se
    establece, es casi seguro que es eso, no un fallo del programa.
  - Lanzar muchas verificaciones seguidas contra el mismo servidor puede
    hacer que ese servidor te liste como IP sospechosa/spam.
"""
import smtplib
import socket
from typing import List, Tuple, Optional
import dns.resolver
import dns.exception

from core.entity_types import Entity
from core.transform_base import Transform, register


# Remite usado en el diálogo SMTP -- no se envía ningún correo real (se corta
# antes de DATA), pero el protocolo exige indicar un remitente en MAIL FROM.
VERIFY_FROM_ADDRESS = "verify@roboteye.local"
CONNECT_TIMEOUT = 10


def _resolve_mx_host(domain: str) -> Optional[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=10)
    except dns.exception.DNSException:
        return None
    if len(answers) == 0:
        return None
    # nos quedamos con el de menor prioridad (preference), el servidor principal
    best = min(answers, key=lambda r: r.preference)
    exchange = str(best.exchange).rstrip(".")
    if not exchange:
        # "Null MX" (RFC 7505): el dominio declara EXPLÍCITAMENTE que no acepta
        # correo (el registro MX es literalmente "."). No es un fallo de DNS,
        # es una declaración a propósito -- no hay ningún servidor al que preguntar.
        return None
    return exchange


@register
class EmailToSMTPVerification(Transform):
    name = "Email → Verificar buzón (SMTP)"
    description = "Conecta al servidor de correo real y comprueba si el buzón existe, sin enviar nada -- TOCA el objetivo, requiere confirmación"
    input_types = ["Email"]
    requires_consent = True

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        if "@" not in entity.value:
            raise RuntimeError(f"'{entity.value}' no parece una dirección de email válida.")
        domain = entity.value.split("@", 1)[1].strip().lower()

        mx_host = _resolve_mx_host(domain)
        if not mx_host:
            raise RuntimeError(
                f"'{domain}' no tiene servidores de correo (MX) publicados, o no se "
                "pudieron resolver. No hay ningún servidor al que preguntar."
            )

        try:
            smtp = smtplib.SMTP(timeout=CONNECT_TIMEOUT)
            smtp.connect(mx_host, 25)
        except (socket.timeout, ConnectionRefusedError, OSError) as ex:
            raise RuntimeError(
                f"No se pudo conectar a {mx_host}:25 ({ex}). Lo más probable es que "
                "tu red bloquee el puerto 25 de salida (muy habitual en redes "
                "residenciales, corporativas y proveedores cloud, precisamente para "
                "frenar spam) -- no es necesariamente un fallo del programa."
            )

        try:
            smtp.helo("roboteye.local")
            smtp.mail(VERIFY_FROM_ADDRESS)
            code, message = smtp.rcpt(entity.value)
        except smtplib.SMTPException as ex:
            raise RuntimeError(f"El servidor {mx_host} cortó la conversación SMTP: {ex}")
        finally:
            try:
                smtp.quit()  # cerramos limpio; en ningún momento se llega a DATA, no se envía nada
            except Exception:
                pass

        message_text = message.decode(errors="ignore") if isinstance(message, bytes) else str(message)

        if code == 250:
            veredicto = "el servidor acepta este destinatario (posible buzón real, o proveedor sin verificación anti-enumeración)"
        elif code in (550, 551, 553):
            veredicto = "el servidor rechaza este destinatario (buzón probablemente inexistente)"
        elif code in (450, 451, 452):
            veredicto = "respuesta ambigua/temporal (greylisting u otra protección anti-spam del servidor)"
        else:
            veredicto = "código de respuesta no estándar, revisar manualmente"

        entity.properties.update({
            "smtp_servidor_mx": mx_host,
            "smtp_codigo_respuesta": code,
            "smtp_mensaje_servidor": message_text.strip(),
            "smtp_veredicto": veredicto,
        })
        return []  # enriquecimiento puro sobre el propio nodo Email, no genera nodos nuevos
