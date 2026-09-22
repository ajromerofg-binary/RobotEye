"""
Transform de consulta a Shodan InternetDB.

Diferencia clave con el escaneo activo que se quitó del proyecto: aquí NO
tocamos el objetivo en ningún momento. Solo consultamos lo que Shodan YA
tiene indexado de esa IP en su base de datos pública -- exactamente igual
de pasivo que consultar crt.sh o Wayback Machine. Es la forma correcta de
tener "inteligencia tipo Shodan" sin cruzar la línea hacia OSINT activo.

InternetDB es un servicio gratuito de Shodan sin autenticación ni API key
(https://internetdb.shodan.io), pensado para lookups rápidos. Solo da
puertos/hostnames/CPEs/tags/CVEs -- no da banners (eso sí requiere la API
de pago). Su base de datos se actualiza semanalmente, así que el dato
puede tener hasta unos días de antigüedad, no es en tiempo real.

Condición de uso del servicio: gratis solo para uso no comercial.
"""
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class IPToShodanInternetDB(Transform):
    name = "IP → Shodan InternetDB (índice pasivo)"
    description = "Consulta lo que Shodan ya tiene indexado de la IP -- gratis, sin key, sin tocar el objetivo"
    input_types = ["IP"]

    API_URL = "https://internetdb.shodan.io/{ip}"

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.API_URL.format(ip=entity.value),
            headers={"User-Agent": "RobotEye-OSINT-Tool"},
            timeout=15,
        )
        if resp.status_code == 404:
            return []  # Shodan no tiene nada indexado de esta IP todavía
        resp.raise_for_status()
        data = resp.json()

        # data.get(key) or [] -- no data.get(key, []) -- cubre TANTO la
        # clave ausente COMO la clave presente con valor null explícito
        # (algunas APIs devuelven null en vez de omitir el campo cuando no
        # hay datos; con .get(key, []) el default solo se aplica si la
        # clave falta, así que un {"cpes": null} real habría crasheado el
        # join(). Bug real encontrado y corregido en la auditoría de esta ronda.
        entity.properties.update({
            "puertos_indexados_shodan": ", ".join(str(p) for p in (data.get("ports") or [])) or "ninguno",
            "cpes_shodan": ", ".join(data.get("cpes") or []) or "ninguno",
            "tags_shodan": ", ".join(data.get("tags") or []) or "ninguno",
            "cves_shodan": ", ".join(data.get("vulns") or []) or "ninguna conocida",
        })

        # Los hostnames que Shodan tiene indexados para esa IP son pivote real:
        # los convertimos en nodos Domain, igual que hace Domain -> IPs a la inversa.
        results = []
        for hostname in (data.get("hostnames") or []):
            results.append((Entity(type="Domain", value=hostname), "hostname (vía Shodan InternetDB)"))
        return results
