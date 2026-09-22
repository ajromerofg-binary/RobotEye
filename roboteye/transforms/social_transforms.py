"""
Transforms de descubrimiento de perfiles en redes sociales a partir de un
username (nueva entidad `Username`).

Se dividen en dos grupos, y es importante distinguirlos:

  1) GitHub y Reddit: tienen API pública real, gratis, sin key. Los datos
     que devuelven son fiables porque vienen directamente de la fuente,
     no de "adivinar" si una URL existe.

  2) El resto de plataformas (LinkedIn, X, Facebook, Instagram, TikTok,
     Pinterest, YouTube, Telegram): NO tienen API pública de consulta por
     username. Se usa la misma técnica pasiva que herramientas como
     Sherlock o Maigret: comprobar si la URL del perfil devuelve una
     página de perfil real o un "no encontrado", sin login y sin leer
     contenido privado.

     Esto es una técnica de OSINT establecida y ampliamente documentada,
     pero NO es infalible -- y hay que ser honesto sobre eso: varias
     plataformas (sobre todo LinkedIn, y en menor medida X/Twitter y
     Facebook) muestran un muro de login/captcha a cualquier visita sin
     sesión iniciada, exista o no el perfil, lo que puede producir falsos
     positivos o falsos negativos. Cada resultado incluye una propiedad
     'confianza' para que sepas cuáles conviene verificar a mano.
"""
from typing import List, Tuple
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import BROWSER_HEADERS as COMMON_HEADERS


@register
class UsernameToGitHub(Transform):
    name = "Username → Perfil de GitHub"
    description = "Comprueba el perfil vía la API pública oficial de GitHub (fiable)"
    input_types = ["Username"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            f"https://api.github.com/users/{entity.value}",
            headers={**COMMON_HEADERS, "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if resp.status_code == 404:
            return []
        if resp.status_code in (403, 429):
            raise RuntimeError(
                "Rate limit de la API pública de GitHub alcanzado (60 peticiones/hora "
                "sin autenticar). Espera un poco y reintenta."
            )
        resp.raise_for_status()
        data = resp.json()

        url_entity = Entity(type="URL", value=data.get("html_url", f"https://github.com/{entity.value}"), properties={
            "plataforma": "GitHub",
            "nombre": data.get("name"),
            "bio": data.get("bio"),
            "empresa": data.get("company"),
            "ubicacion": data.get("location"),
            "blog": data.get("blog"),
            "repos_publicos": data.get("public_repos"),
            "seguidores": data.get("followers"),
            "cuenta_creada": data.get("created_at"),
            "confianza": "alta (API oficial)",
        })
        return [(url_entity, "perfil en GitHub")]


@register
class UsernameToReddit(Transform):
    name = "Username → Perfil de Reddit"
    description = "Comprueba el perfil vía la API JSON pública de Reddit (fiable)"
    input_types = ["Username"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            f"https://www.reddit.com/user/{entity.value}/about.json",
            headers=COMMON_HEADERS,
            timeout=10,
        )
        if resp.status_code == 404:
            return []
        if resp.status_code == 429:
            raise RuntimeError("Rate limit de Reddit alcanzado. Espera un poco y reintenta.")
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            return []

        url_entity = Entity(type="URL", value=f"https://www.reddit.com/user/{entity.value}", properties={
            "plataforma": "Reddit",
            "karma_total": data.get("total_karma"),
            "cuenta_creada_epoch": data.get("created_utc"),
            "verificado": data.get("verified"),
            "cuenta_de_pago_(gold)": data.get("is_gold"),
            "confianza": "alta (API oficial)",
        })
        return [(url_entity, "perfil en Reddit")]


# (nombre de la plataforma, plantilla de URL, nivel de confianza honesto)
# La confianza refleja cómo de agresivamente bloquea esa plataforma las
# comprobaciones automatizadas sin sesión iniciada, según el comportamiento
# público y documentado de cada una en herramientas tipo Sherlock/Maigret.
FRAGILE_PLATFORMS = [
    ("X (Twitter)", "https://x.com/{u}",
     "baja (X redirige a login para visitantes sin sesión desde 2023; poco fiable)"),
    ("Facebook", "https://www.facebook.com/{u}",
     "baja (Facebook suele mostrar muro de login exista o no el perfil)"),
    ("LinkedIn", "https://www.linkedin.com/in/{u}",
     "muy baja (LinkedIn bloquea agresivamente cualquier visita sin sesión; alto riesgo de falso resultado)"),
    ("Instagram", "https://www.instagram.com/{u}/",
     "media (a veces accesible sin login, pero limita mucho por IP)"),
    ("TikTok", "https://www.tiktok.com/@{u}",
     "media"),
    ("Pinterest", "https://www.pinterest.com/{u}/",
     "media"),
    ("YouTube", "https://www.youtube.com/@{u}",
     "media"),
    ("Telegram", "https://t.me/{u}",
     "media"),
]


@register
class UsernameToSocialProfiles(Transform):
    name = "Username → Otras redes (comprobación pasiva, verificar a mano)"
    description = "Comprueba X, Facebook, LinkedIn, Instagram, TikTok, Pinterest, YouTube y Telegram (técnica tipo Sherlock, sin API — revisar resultados)"
    input_types = ["Username"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        results = []
        for platform_name, url_template, confianza in FRAGILE_PLATFORMS:
            url = url_template.format(u=entity.value)
            try:
                resp = requests.get(url, headers=COMMON_HEADERS, timeout=10, allow_redirects=True)
            except requests.RequestException:
                continue  # esa plataforma concreta no respondió, seguimos con las demás

            if resp.status_code == 200:
                url_entity = Entity(type="URL", value=url, properties={
                    "plataforma": platform_name,
                    "confianza": confianza,
                    "http_status": resp.status_code,
                })
                results.append((url_entity, f"posible perfil en {platform_name}"))
        return results


@register
class UsernameToGitLab(Transform):
    name = "Username → Perfil de GitLab"
    description = "Comprueba el perfil vía la API pública oficial de GitLab (fiable)"
    input_types = ["Username"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        resp = requests.get(
            "https://gitlab.com/api/v4/users",
            params={"username": entity.value},
            headers=COMMON_HEADERS,
            timeout=10,
        )
        if resp.status_code in (403, 429):
            raise RuntimeError("Rate limit de la API pública de GitLab alcanzado. Espera un poco y reintenta.")
        resp.raise_for_status()
        data = resp.json()

        # La API de búsqueda de GitLab devuelve una LISTA (vacía si no hay
        # coincidencia), a diferencia de la de GitHub que da 404 directo.
        if not data:
            return []

        perfil = data[0]
        url_entity = Entity(type="URL", value=perfil.get("web_url", f"https://gitlab.com/{entity.value}"), properties={
            "plataforma": "GitLab",
            "nombre": perfil.get("name"),
            "estado": perfil.get("state"),
        })
        return [(url_entity, "perfil de GitLab")]
