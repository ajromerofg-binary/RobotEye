"""
Transform de email harvesting (estilo theHarvester): busca direcciones de
email públicas asociadas a un dominio.

Técnica: búsqueda + lectura de páginas públicas ya indexadas por un
buscador -- el mismo nivel de contacto que el resto de transforms basadas
en DuckDuckGo de este proyecto (Google Dorking, Organization → Dominio
probable). No se sondea ni se toca el dominio objetivo directamente: se
consulta a un tercero (DuckDuckGo) y se leen páginas públicas que ese
tercero ya ha indexado -- el mismo "nivel de contacto" que ya tiene
`URLToDocumentMetadata` al descargar un documento enlazado desde una
búsqueda. Por eso esta transform es pasiva, no requiere consentimiento.

Limitaciones honestas:
  - Solo encuentra emails que YA estén publicados en alguna página indexada
    por DuckDuckGo. No adivina ni genera direcciones -- a diferencia de
    `Person → Usernames probables`, aquí todo resultado es un hallazgo real
    de una página pública concreta, no un candidato sin verificar.
  - Cobertura parcial por diseño: un dominio puede tener decenas de
    direcciones reales sin ninguna publicada nunca en una página indexable.
    Ausencia de resultados no significa que el dominio "no tenga emails".
  - Si una de las páginas encontradas no responde o tarda, se descarta esa
    página concreta y se sigue con las demás -- un fallo puntual no aborta
    la búsqueda completa.
"""
import re
from typing import List, Tuple, Set
import requests

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.dorking_transforms import DorkToResults, BROWSER_HEADERS as COMMON_HEADERS, is_ddg_blocked, DDG_BLOCK_MESSAGE  # reutilizamos su parseo de resultados DDG y sus cabeceras realistas, ya probadas




def _extract_emails(text: str, domain: str) -> Set[str]:
    pattern = re.compile(r"[a-zA-Z0-9._%+\-]+@" + re.escape(domain), re.IGNORECASE)
    return {m.group(0).lower() for m in pattern.finditer(text)}


@register
class DomainToEmailHarvest(Transform):
    name = "Domain → Emails (búsqueda web, estilo theHarvester)"
    description = "Busca direcciones de email publicadas del dominio en páginas ya indexadas (gratis, sin key)"
    input_types = ["Domain"]
    uses_ddg = True

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    MAX_PAGES_TO_FETCH = 5
    PAGE_FETCH_TIMEOUT = 10

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        domain = entity.value
        resp = requests.get(
            self.SEARCH_URL,
            params={"q": f'"@{domain}"'},
            headers=COMMON_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        if is_ddg_blocked(resp.text):
            raise RuntimeError(DDG_BLOCK_MESSAGE)

        found_emails: Set[str] = set()
        # 1) emails visibles directamente en los snippets de resultado -- gratis,
        # ya los tenemos en la respuesta de búsqueda, sin petición extra.
        found_emails |= _extract_emails(resp.text, domain)

        # 2) visitamos las primeras páginas encontradas por si el email
        # aparece en el cuerpo de la página pero no en el snippet corto.
        urls = DorkToResults.parse_results(resp.text, limit=self.MAX_PAGES_TO_FETCH)
        for url in urls:
            try:
                page_resp = requests.get(url, headers=COMMON_HEADERS, timeout=self.PAGE_FETCH_TIMEOUT)
            except requests.RequestException:
                continue  # esa página en concreto no respondió, seguimos con las demás
            if page_resp.status_code != 200:
                continue
            found_emails |= _extract_emails(page_resp.text, domain)

        results = []
        for email in sorted(found_emails):
            email_entity = Entity(type="Email", value=email, properties={
                "origen": "encontrado en búsqueda web -- verificar el contexto de la página fuente",
            })
            results.append((email_entity, "email encontrado en búsqueda"))
        return results
