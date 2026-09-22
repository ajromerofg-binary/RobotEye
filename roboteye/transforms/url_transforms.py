"""
Transform universal para cualquier entidad `URL`.

Se detectó durante una auditoría de cobertura que `URL` tenía técnicamente
una transform registrada (`URLToDocumentMetadata`), pero solo se activa si
el valor termina en `.pdf`/`.docx`/`.xlsx` -- la inmensa mayoría de URLs que
genera el resto del proyecto (perfiles de GitHub/Reddit, snapshots de
Wayback Machine, resultados de dorks que no son documentos, resultados de
"Otras redes"...) NO cumplen eso, así que se quedaban sin ninguna acción
disponible. Mismo problema que tenía `Organization`, solo que condicionado
al valor en vez de al tipo.

Esta transform se aplica a CUALQUIER URL sin excepción: extrae el dominio
de forma puramente local (sin red) para poder pivotar de vuelta a todo el
ecosistema de transforms de `Domain` que ya existe, sea cual sea el origen
de esa URL.
"""
from typing import List, Tuple
from urllib.parse import urlparse

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class URLToDomain(Transform):
    name = "URL → Dominio"
    description = "Extrae el dominio de la URL para pivotar a las transforms de Domain (local, sin red)"
    input_types = ["URL"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        # .hostname (no .netloc) gestiona correctamente credenciales
        # embebidas (user:pass@host) y el puerto -- un split manual por ":"
        # se equivoca con URLs tipo "https://user:pass@x.com:8443/a" (corta
        # en el primer ":", que es el de user:pass, no el del puerto).
        host = urlparse(entity.value).hostname
        host = host.lower() if host else None
        if host and host.startswith("www."):
            host = host[4:]
        if not host:
            raise RuntimeError(f"No se pudo extraer un dominio válido de '{entity.value}'.")
        return [(Entity(type="Domain", value=host), "dominio de la URL")]
