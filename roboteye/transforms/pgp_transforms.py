"""
Transform de comprobación de clave PGP pública para un email.

Nota de corrección de diseño, para que quede constancia: la idea original
era "Domain → Emails vía PGP keyservers" (email harvesting por dominio),
pero keys.openpgp.org NO soporta esa búsqueda por diseño explícito de
privacidad -- su propia documentación dice literalmente "Only exact
matches by email address, fingerprint or long key id are returned". No
hay forma de listar todos los emails de un dominio desde ahí, así que esa
versión no era viable y se descartó antes de escribir una sola línea que
fingiera que sí lo era.

Lo que SÍ es viable y útil: comprobar si un email CONCRETO que ya tienes
en el grafo tiene una clave pública PGP asociada. Publicar la clave ahí es
opt-in explícito (el propietario tiene que verificar el email por correo),
así que un resultado positivo confirma que el email es real, activo, y que
su dueño usa cifrado -- un dato de perfilado razonable, aunque no "cosecha"
ningún email nuevo, solo enriquece uno que ya tenías.
"""
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class EmailToPGPKey(Transform):
    name = "Email → Clave PGP (keys.openpgp.org)"
    description = "Comprueba si el email tiene una clave pública PGP verificada (gratis, sin key)"
    input_types = ["Email"]

    API_URL = "https://keys.openpgp.org/vks/v1/by-email/{email}"

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.API_URL.format(email=entity.value),
            headers={"User-Agent": "RobotEye-OSINT-Tool"},
            timeout=15,
        )
        if resp.status_code == 404:
            return []  # sin clave pública verificada para este email, no es un error
        if resp.status_code == 429:
            raise RuntimeError(
                "Rate limit de keys.openpgp.org alcanzado (1 petición/min por email). "
                "Espera un poco y reintenta."
            )
        resp.raise_for_status()

        armored_key = resp.text.strip()
        preview = armored_key[:300] + ("..." if len(armored_key) > 300 else "")

        entity.properties.update({
            "clave_pgp_publica": "sí, verificada (opt-in del propietario)",
            "clave_pgp_ascii_armored_preview": preview,
        })
        return []  # enriquecimiento puro sobre el email existente, no genera nodos nuevos
