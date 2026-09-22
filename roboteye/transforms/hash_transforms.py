"""
Transform de identificación de tipo de hash, por prefijo y longitud.

100% local, sin red -- encaja con lo que sacas de brechas (XposedOrNot) o
de un CTF/pentest, para saber qué algoritmo tienes delante antes de
intentar crackearlo.

Importante sobre ambigüedad: los hashes hexadecimales "planos" (sin prefijo
identificador) no son únicos por longitud -- MD5, NTLM y LM hash comparten
exactamente 32 caracteres hex, por ejemplo. En esos casos se listan TODOS
los candidatos plausibles en vez de afirmar uno con falsa certeza; solo el
contexto de dónde salió el hash (un SAM de Windows, un dump MySQL...) lo
puede desambiguar de verdad.
"""
import re
from typing import List, Tuple

from core.entity_types import Entity
from core.transform_base import Transform, register


# Hashes con prefijo identificador propio -- sin ambigüedad posible
PREFIXED_PATTERNS = [
    (re.compile(r"^\$2[aby]\$"), "bcrypt"),
    (re.compile(r"^\$1\$"), "MD5 crypt (Unix)"),
    (re.compile(r"^\$5\$"), "SHA-256 crypt (Unix)"),
    (re.compile(r"^\$6\$"), "SHA-512 crypt (Unix)"),
    (re.compile(r"^\$y\$|^\$argon2"), "Argon2"),
    (re.compile(r"^\$P\$|^\$H\$"), "phpBB / WordPress (MD5 salteado)"),
]

# Longitud exacta en hex -> candidatos posibles (varios si comparten longitud)
HEX_LENGTH_CANDIDATES = {
    32: ["MD5", "NTLM", "LM hash"],
    40: ["SHA-1"],
    56: ["SHA-224", "SHA3-224"],
    64: ["SHA-256", "SHA3-256"],
    96: ["SHA-384", "SHA3-384"],
    128: ["SHA-512", "SHA3-512"],
}

HEX_RE = re.compile(r"^[a-fA-F0-9]+$")


@register
class HashIdentifyType(Transform):
    name = "Hash → Identificar tipo"
    description = "Identifica el algoritmo probable por prefijo/longitud (cálculo local, sin red)"
    input_types = ["Hash"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        value = entity.value.strip()

        for pattern, name in PREFIXED_PATTERNS:
            if pattern.match(value):
                entity.properties["tipo_identificado"] = name
                entity.properties["ambiguo"] = "no"
                return []

        if HEX_RE.match(value):
            candidates = HEX_LENGTH_CANDIDATES.get(len(value))
            if candidates:
                entity.properties["tipos_candidatos"] = ", ".join(candidates)
                entity.properties["ambiguo"] = "sí" if len(candidates) > 1 else "no"
                entity.properties["longitud_hex"] = len(value)
                return []

        raise RuntimeError(
            f"No se reconoce el formato de '{value[:24]}{'...' if len(value) > 24 else ''}' "
            "como ningún tipo de hash habitual (ni hex de longitud conocida, ni con prefijo $tipo$)."
        )
