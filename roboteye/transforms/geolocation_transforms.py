"""
Transform de geolocalización aproximada de una IP, vía ip-api.com (gratis,
sin key, uso no comercial). Complementa a `IP → ASN` (Team Cymru, que solo
da país) con ciudad/región/coordenadas aproximadas y el ISP.

Aviso importante, para no venderlo como algo que no es -- lo mismo que ya
se avisa en el análisis de teléfonos de este proyecto: esto ubica la
infraestructura de red (dónde está el ISP/datacenter que anuncia ese rango
de IP), NO la posición GPS real de ningún dispositivo o persona. Para VPNs,
CDNs (Cloudflare, etc.) o proxies, la ciudad devuelta puede no tener
relación real con dónde está el usuario final -- por eso se incluyen los
flags 'proxy'/'hosting' que da la propia API, para saber cuándo desconfiar
del dato.

Nota técnica: el tier gratuito de ip-api.com solo funciona por HTTP plano,
sin HTTPS (limitación de su plan gratuito; HTTPS es solo de pago). El dato
enviado es únicamente la IP a consultar, nada sensible, pero queda dicho
para que no sorprenda ver 'http://' en vez de 'https://' en el código.
"""
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register


@register
class IPToGeolocation(Transform):
    name = "IP → Geolocalización aproximada"
    description = "Ciudad/región/ISP aproximados de la IP (gratis, sin key -- ver aviso de precisión)"
    input_types = ["IP"]

    API_URL = "http://ip-api.com/json/{ip}"

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            self.API_URL.format(ip=entity.value),
            params={"fields": "status,message,country,regionName,city,lat,lon,isp,org,proxy,hosting"},
            timeout=15,
        )
        if resp.status_code == 429:
            raise RuntimeError("Rate limit de ip-api.com alcanzado (45 peticiones/min). Espera un poco y reintenta.")
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            return []  # IP privada, reservada, o no geolocalizable por su naturaleza

        entity.properties.update({
            "pais": data.get("country") or "desconocido",
            "region": data.get("regionName") or "desconocida",
            "ciudad": data.get("city") or "desconocida",
            "coordenadas_aprox": (
                f"{data.get('lat')}, {data.get('lon')}"
                if data.get("lat") is not None and data.get("lon") is not None
                else "desconocidas"
            ),
            "isp": data.get("isp") or "desconocido",
            "organizacion": data.get("org") or "desconocida",
            "posible_proxy_vpn": "sí" if data.get("proxy") else "no",
            "posible_datacenter_hosting": "sí" if data.get("hosting") else "no",
        })
        return []  # enriquecimiento puro sobre el propio nodo IP, no genera nodos nuevos
