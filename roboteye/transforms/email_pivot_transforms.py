"""
Transforms de pivote desde una entidad Email.

Hueco que cerraban en Maltego "EmailAddress → Domain [DNS]" y
"EmailAddress → Person [Parse separator]": con las nuevas fuentes de email
del proyecto (harvesting, WHOIS, pastes, metadatos de documentos...) el
grafo genera muchos nodos Email, pero hasta ahora no había forma de pivotar
DE VUELTA hacia Domain, ni de intentar extraer un nombre de persona del
propio formato del email. Ambas 100% locales, sin red.
"""
import re
from typing import List, Tuple

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class EmailToDomain(Transform):
    name = "Email → Dominio"
    description = "Extrae el dominio del email para pivotar de vuelta a todo el ecosistema de Domain (sin red)"
    input_types = ["Email"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        if "@" not in entity.value:
            raise RuntimeError(f"'{entity.value}' no parece una dirección de email válida (falta '@').")
        domain = entity.value.rsplit("@", 1)[1].strip().lower()
        if not domain:
            raise RuntimeError(f"'{entity.value}' no tiene un dominio reconocible tras la '@'.")
        return [(Entity(type="Domain", value=domain), "dominio del email")]


# Separadores típicos en emails corporativos (nombre.apellido@, nombre_apellido@...)
_SEPARATOR_RE = re.compile(r"[._\-]+")


@register
class EmailToPersonGuess(Transform):
    name = "Email → Persona probable (heurística)"
    description = "Intenta extraer un nombre de persona del formato del email (candidato sin verificar, cálculo local)"
    input_types = ["Email"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        if "@" not in entity.value:
            raise RuntimeError(f"'{entity.value}' no parece una dirección de email válida.")
        local_part = entity.value.split("@", 1)[0]

        parts = [p for p in _SEPARATOR_RE.split(local_part) if p.isalpha() and len(p) > 1]
        if len(parts) < 2:
            # buzones genéricos (info@, contacto@, admin@...) no tienen separación
            # nombre.apellido reconocible -- no forzamos una suposición sin base.
            return []

        nombre_probable = " ".join(p.capitalize() for p in parts)
        person_entity = Entity(type="Person", value=nombre_probable, properties={
            "origen": "heurística a partir del formato del email (nombre.apellido@...), NO verificado",
        })
        return [(person_entity, "persona probable (formato del email)")]
