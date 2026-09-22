"""
Transform de análisis de números de teléfono.

100% nativo y offline: usa `phonenumbers` (el port en Python de la librería
libphonenumber de Google), que trae sus propias bases de datos de rangos
numéricos, prefijos de operador y husos horarios embebidas en el paquete.
No hace ninguna petición de red, no necesita API key, y funciona sin
conexión a internet.

Honestidad sobre los límites de esta técnica (importante, para no venderla
como algo que no es):
  - La "ubicación" que da es la zona de asignación del prefijo/rango del
    número (ciudad/provincia/país), NO la posición GPS real del teléfono.
    Eso no existe como consulta pública, ni de pago ni gratis; solo los
    operadores y las fuerzas de seguridad con orden judicial pueden
    triangular la posición real de un teléfono.
  - El operador (compañía) que devuelve es el operador ORIGINAL al que se
    le asignó ese rango de numeración. Si el número se ha portado a otra
    compañía (algo muy común), el dato puede estar desactualizado — la
    portabilidad no se refleja en estas bases de datos offline.
"""
from typing import List, Tuple
import phonenumbers
from phonenumbers import geocoder, carrier, timezone as pn_timezone

from core.entity_types import Entity
from core.transform_base import Transform, register


_NUMBER_TYPE_NAMES = {
    phonenumbers.PhoneNumberType.MOBILE: "Móvil",
    phonenumbers.PhoneNumberType.FIXED_LINE: "Fijo",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fijo o móvil",
    phonenumbers.PhoneNumberType.TOLL_FREE: "Número gratuito",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "Tarificación especial",
    phonenumbers.PhoneNumberType.VOIP: "VoIP",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Número personal",
    phonenumbers.PhoneNumberType.PAGER: "Buscapersonas",
    phonenumbers.PhoneNumberType.UAN: "UAN",
    phonenumbers.PhoneNumberType.UNKNOWN: "Desconocido",
}


@register
class PhoneAnalysis(Transform):
    name = "Phone → Análisis (país, operador, tipo)"
    description = "Analiza el número offline: país, zona, operador original, tipo y huso horario"
    input_types = ["Phone"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        # Si el número no viene con prefijo internacional, phonenumbers no
        # puede parsearlo sin saber el país por defecto. Intentamos parsearlo
        # tal cual (asume formato internacional +34...) primero.
        try:
            parsed = phonenumbers.parse(entity.value, None)
        except phonenumbers.NumberParseException:
            raise RuntimeError(
                f"No se pudo interpretar '{entity.value}' como número de teléfono. "
                "Usa formato internacional con prefijo, ej: +34600123456."
            )

        if not phonenumbers.is_valid_number(parsed):
            raise RuntimeError(
                f"'{entity.value}' no es un número de teléfono válido según el plan "
                "de numeración de ese país (formato correcto, pero rango no asignado)."
            )

        pais = geocoder.description_for_number(parsed, "es") or "desconocido"
        operador = carrier.name_for_number(parsed, "es") or "desconocido / portado a otra compañía"
        tipo = _NUMBER_TYPE_NAMES.get(phonenumbers.number_type(parsed), "Desconocido")
        husos = ", ".join(pn_timezone.time_zones_for_number(parsed)) or "desconocido"
        region_iso = phonenumbers.region_code_for_number(parsed) or "??"
        formato_internacional = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)

        # Enriquecemos el propio nodo Phone con todos los datos (igual que WHOIS
        # hace sobre Domain), en vez de generar nodos nuevos: aquí no hay una
        # "entidad relacionada" real que pivotar, es información sobre el propio número.
        entity.properties.update({
            "pais_region": pais,
            "codigo_pais_iso": region_iso,
            "operador_original": operador,
            "tipo_numero": tipo,
            "huso_horario": husos,
            "formato_internacional": formato_internacional,
        })

        # Generamos un nodo Organization solo si hay un operador identificado
        # de verdad (no el texto de "desconocido"), para poder pivotar desde ahí.
        if carrier.name_for_number(parsed, "es"):
            org_entity = Entity(type="Organization", value=operador, properties={
                "rol": "operador de telefonía (asignación original del rango)",
            })
            return [(org_entity, "operador original del número")]
        return []
