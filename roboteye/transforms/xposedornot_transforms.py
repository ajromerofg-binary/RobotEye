"""
Transform de comprobación de brechas de datos y "pastes" (Pastebin y sitios
similares).

Usa XposedOrNot (https://xposedornot.com) en vez de HaveIBeenPwned: HIBP dejó
de permitir comprobar breaches de un email de forma gratuita desde su API v3
(hace falta suscripción de pago). XposedOrNot es una alternativa genuinamente
gratuita, open source y sin API key para exactamente el mismo caso de uso
-- de hecho da más detalle por breach (industria, riesgo de la contraseña,
descripción completa) que la propia HIBP.

El mismo endpoint (`breach-analytics`) devuelve también, en la misma
respuesta y sin coste de otra petición, si el email aparece en algún
"paste" (fragmento de texto filtrado en sitios tipo Pastebin) -- lo
aprovechamos aquí sin gastar una consulta extra del límite de rate.

Nota de transparencia: la documentación pública de XposedOrNot no publica un
ejemplo completo del bloque ExposedPastes (en su ejemplo de referencia esa
cuenta no tenía pastes, así que sale `null`). Por eso el parseo de pastes es
deliberadamente defensivo: en vez de asumir nombres de campo concretos,
vuelca todos los campos que vengan tal cual como propiedades de la entidad,
así no se pierde ni se rompe nada si el esquema real difiere un poco de lo
esperado.

Límites del tier gratuito por IP (no hace falta gestionar nada, solo saberlo
si se lanza en bucle sobre muchos emails seguidos): 2 peticiones/segundo,
25/hora, 100/día en el endpoint breach-analytics.

Fuente / documentación: https://xposedornot.com/api_doc
"""
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class EmailToBreachesXposedOrNot(Transform):
    name = "Email → Breaches y Pastes (XposedOrNot)"
    description = "Comprueba brechas de datos y menciones en pastes conocidas (gratis, sin API key)"
    input_types = ["Email"]

    API_URL = "https://api.xposedornot.com/v1/breach-analytics"

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.API_URL,
            params={"email": entity.value},
            headers={"User-Agent": "RobotEye-OSINT-Tool"},
            timeout=15,
        )

        if resp.status_code == 429:
            raise RuntimeError(
                "Rate limit de XposedOrNot alcanzado (tier gratuito: 2 peticiones/seg, "
                "25/hora, 100/día por IP). Espera un poco y reintenta."
            )
        if resp.status_code == 404:
            return []  # email no encontrado en su base de datos, no es un error

        resp.raise_for_status()
        data = resp.json()

        results = []
        results.extend(self._parse_breaches(data))
        results.extend(self._parse_pastes(data))
        return results

    @staticmethod
    def _parse_breaches(data: dict) -> List[Tuple[Entity, str]]:
        exposed = data.get("ExposedBreaches")
        if not exposed or not exposed.get("breaches_details"):
            return []

        results = []
        for b in exposed["breaches_details"]:
            props = {
                "fecha_brecha": b.get("xposed_date"),
                "registros_expuestos": b.get("xposed_records"),
                "tipos_datos_expuestos": b.get("xposed_data"),
                "riesgo_contraseña": b.get("password_risk"),
                "industria": b.get("industry"),
                "verificada": b.get("verified"),
                "dominio_origen": b.get("domain"),
                "descripcion": b.get("details"),
            }
            breach_entity = Entity(type="Breach", value=b.get("breach", "desconocida"), properties=props)
            results.append((breach_entity, "aparece en brecha"))
        return results

    @staticmethod
    def _parse_pastes(data: dict) -> List[Tuple[Entity, str]]:
        exposed_pastes = data.get("ExposedPastes")
        if not exposed_pastes:
            return []  # sin pastes conocidos para este email, o campo null (email limpio en pastes)

        results = []
        for i, paste in enumerate(exposed_pastes):
            if not isinstance(paste, dict):
                continue
            # Volcado defensivo: no asumimos nombres de campo concretos (ver nota
            # de transparencia arriba), así que usamos cualquier campo descriptivo
            # disponible como label, y el resto tal cual como propiedades.
            label = paste.get("Source") or paste.get("Title") or paste.get("Id") or paste.get("id") or f"paste #{i + 1}"
            paste_entity = Entity(type="Paste", value=str(label), properties=dict(paste))
            results.append((paste_entity, "aparece en paste"))
        return results
