"""
Dos transforms nuevas para `Email`, cerrando huecos de la auditoría de
cobertura de esta ronda:

- `Email → Gravatar`: comprueba si el email tiene un perfil público en
  Gravatar (servicio de avatares ligado a WordPress.com, usado por
  millones de sitios). Técnica OSINT clásica: el hash del email revela si
  existe un perfil, y a veces el perfil público incluye nombre real,
  ubicación o enlaces a otras redes. Gravatar migró su hash de MD5 a
  SHA256 (ver docs.gravatar.com) -- se usa SHA256 aquí. Sin API key: se
  consulta el endpoint clásico `gravatar.com/<hash>.json`, que solo
  requiere autenticación para las funciones avanzadas de la API v3, no
  para esta comprobación básica de existencia.
- `Email → Username probable`: la parte local de un email (antes de la
  arroba) es a menudo, literalmente, el username que esa persona usa en
  otras plataformas -- un pivote local, sin red, hacia el ecosistema de
  transforms de `Username` ya existente (GitHub, Reddit, otras redes).
"""
import hashlib
import re
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import BROWSER_HEADERS


@register
class EmailToGravatar(Transform):
    name = "Email → Gravatar"
    description = "Comprueba si el email tiene un perfil público en Gravatar (nombre, ubicación, enlaces si los hay)"
    input_types = ["Email"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        email_hash = hashlib.sha256(entity.value.strip().lower().encode()).hexdigest()
        resp = requests.get(
            f"https://gravatar.com/{email_hash}.json",
            headers=BROWSER_HEADERS,
            timeout=10,
        )
        if resp.status_code == 404:
            entity.properties["gravatar"] = "sin perfil público"
            return []
        resp.raise_for_status()
        data = resp.json()

        entradas = (data.get("entry") or [{}])
        perfil = entradas[0] if entradas else {}

        entity.properties.update({
            "gravatar": "tiene perfil público",
            "gravatar_nombre": perfil.get("displayName") or "no publicado",
            "gravatar_url": perfil.get("profileUrl") or f"https://gravatar.com/{email_hash}",
        })

        results = []
        ubicacion = perfil.get("currentLocation")
        if ubicacion:
            entity.properties["gravatar_ubicacion"] = ubicacion
        for cuenta in perfil.get("accounts", []) or []:
            url = cuenta.get("url")
            if url:
                results.append((Entity(type="URL", value=url, properties={
                    "plataforma": cuenta.get("shortname") or cuenta.get("name") or "desconocida",
                }), "cuenta enlazada en el perfil de Gravatar"))
        return results


# Buzones de rol/genéricos: no tiene sentido tratar "info", "admin", etc.
# como si fueran el username personal de alguien -- generarían ruido, no
# una pista real.
GENERIC_LOCAL_PARTS = {
    "info", "admin", "contact", "contacto", "support", "soporte", "sales",
    "ventas", "hello", "hola", "hi", "no-reply", "noreply", "webmaster",
    "postmaster", "abuse", "help", "ayuda", "office", "team", "equipo",
    "marketing", "press", "prensa", "jobs", "careers", "rrhh", "hr",
}


@register
class EmailToUsernameGuess(Transform):
    name = "Email → Username probable"
    description = "Usa la parte local del email como candidato de username en otras plataformas (descarta buzones genéricos)"
    input_types = ["Email"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        if "@" not in entity.value:
            raise RuntimeError(f"'{entity.value}' no parece una dirección de email válida.")
        local_part = entity.value.split("@", 1)[0].strip().lower()

        if local_part in GENERIC_LOCAL_PARTS:
            raise RuntimeError(
                f"'{local_part}' es un buzón genérico/de rol, no el username personal "
                "de nadie -- no se genera ningún candidato para evitar ruido."
            )

        # limpiamos separadores típicos de email (punto, guión) que rara vez
        # sobreviven tal cual en un username real de otra plataforma
        candidato = re.sub(r"[._]", "", local_part)
        candidatos = {local_part, candidato} if candidato != local_part else {local_part}
        candidatos = {c for c in candidatos if len(c) >= 2}

        if not candidatos:
            return []

        return [
            (Entity(type="Username", value=c, properties={
                "origen": f"derivado de la parte local de {entity.value} -- candidato sin verificar",
            }), "posible username derivado del email")
            for c in sorted(candidatos)
        ]
