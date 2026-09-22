"""
`MACAddress → Fabricante`: identifica el fabricante del dispositivo a
partir de los primeros 3 bytes de su dirección MAC (el OUI,
Organizationally Unique Identifier, asignado por el IEEE a cada
fabricante). Técnica clásica de análisis de redes: saber quién fabricó
una tarjeta de red revela a menudo el tipo de dispositivo (routers de una
marca concreta, un móvil, una cámara IP...).

Se usa la API pública de macvendors.com en vez de mantener una copia local
de la base de datos del IEEE (decenas de miles de entradas -- 58.000 solo
en el registro MA-L -- que quedaría desactualizada sin mantenimiento
activo, algo que este proyecto no puede ofrecer). La API es gratis, sin
API key, hasta 1000 consultas/día -- de sobra para uso puntual de OSINT.
"""
import requests
from typing import List, Tuple

from core.entity_types import Entity
from core.transform_base import Transform, register

MACVENDORS_API_URL = "https://api.macvendors.com/"


@register
class MACAddressToVendor(Transform):
    name = "MACAddress → Fabricante"
    description = "Identifica el fabricante del dispositivo a partir del OUI (macvendors.com, gratis, sin key)"
    input_types = ["MACAddress"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            MACVENDORS_API_URL + entity.value.strip(),
            timeout=10,
            headers={"User-Agent": "RobotEye-OSINT-Tool"},
        )
        if resp.status_code == 404:
            raise RuntimeError(
                f"'{entity.value}' no coincide con ningún fabricante conocido en el "
                "registro del IEEE (puede ser una MAC generada aleatoriamente, cada vez "
                "más habitual por privacidad en móviles y portátiles modernos)."
            )
        if resp.status_code == 429:
            raise RuntimeError(
                "Límite diario de macvendors.com alcanzado (1000 consultas/día sin API "
                "key). Reintenta más tarde."
            )
        resp.raise_for_status()

        vendor = resp.text.strip()
        if not vendor:
            raise RuntimeError(f"'{entity.value}' no devolvió ningún fabricante.")

        entity.properties["fabricante"] = vendor
        return []  # enriquecimiento puro sobre el propio nodo, no genera nodos nuevos
