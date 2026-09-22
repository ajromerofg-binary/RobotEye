"""
`Hash → Comprobar en Pwned Passwords`: comprueba si un hash SHA-1 (el
formato que usa la API) corresponde a una contraseña que ya ha aparecido
en alguna filtración conocida, usando la API de k-anonimato de "Have I
Been Pwned" -- Pwned Passwords.

Es una de las pocas técnicas de este tipo que se puede hacer de forma
genuinamente privada: solo se envían los 5 primeros caracteres del hash,
nunca el hash completo ni la contraseña -- el servidor devuelve todos los
sufijos que empiezan por esos 5 caracteres (varios cientos), y la
comparación final del sufijo completo se hace en local. La API nunca ve
qué contraseña exacta se está consultando.

Solo tiene sentido para hashes de 40 caracteres hex (SHA-1). Si el hash
identificado por `Hash → Identificar tipo` es de otro tipo, esta transform
no aplica (ver `applies_to`).
"""
import re
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register

SHA1_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")


@register
class HashToPwnedPasswords(Transform):
    name = "Hash → Comprobar en Pwned Passwords (k-anonimato)"
    description = "Comprueba si un hash SHA-1 corresponde a una contraseña ya filtrada, sin revelar el hash completo (HaveIBeenPwned)"
    input_types = ["Hash"]

    API_URL = "https://api.pwnedpasswords.com/range/"

    def applies_to(self, entity: Entity) -> bool:
        return entity.type == "Hash" and bool(SHA1_PATTERN.match(entity.value.strip()))

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        hash_upper = entity.value.strip().upper()
        prefix, suffix = hash_upper[:5], hash_upper[5:]

        resp = requests.get(
            self.API_URL + prefix,
            headers={"User-Agent": "RobotEye-OSINT-Tool", "Add-Padding": "true"},
            timeout=15,
        )
        resp.raise_for_status()

        veces_visto = 0
        for linea in resp.text.splitlines():
            if ":" not in linea:
                continue
            sufijo_linea, count = linea.split(":", 1)
            if sufijo_linea.strip().upper() == suffix:
                veces_visto = int(count.strip())
                break

        if veces_visto > 0:
            entity.properties["pwned_passwords"] = (
                f"SÍ -- esta contraseña ha aparecido en filtraciones conocidas "
                f"{veces_visto} veces. No debería usarse en ningún sitio."
            )
        else:
            entity.properties["pwned_passwords"] = (
                "no encontrada en el corpus de Pwned Passwords -- no aparece en las "
                "filtraciones que HaveIBeenPwned tiene indexadas (no es garantía "
                "absoluta de que sea una contraseña fuerte, solo de que no está en ese corpus)"
            )
        return []
