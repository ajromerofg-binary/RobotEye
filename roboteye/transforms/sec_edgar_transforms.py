"""
`Organization → Registro SEC (EDGAR)`: consulta el registro oficial de la
SEC de EEUU (U.S. Securities and Exchange Commission) para confirmar la
razón social exacta, el CIK (Central Index Key, el identificador único
que la SEC asigna a cada declarante), la clasificación SIC (código y
descripción de industria), el estado de incorporación, los tickers y
mercados donde cotiza -- más los últimos ingresos y beneficio neto
reportados en su 10-K más reciente.

Por qué esta fuente y no OpenCorporates: se investigó antes de escribir
código, y OpenCorporates eliminó su tier gratuito en 2026 (ahora exige
un plan de pago desde varios miles de euros al año). SEC EDGAR sigue
siendo 100% pública y gratuita -- sin API key, solo exige una cabecera
User-Agent identificable y respetar 10 peticiones/segundo.

Limitación honesta e importante, la misma que ya se documenta en el
manual: SEC EDGAR solo cubre empresas que declaran ante la SEC de
EEUU -- en la práctica, empresas públicas estadounidenses (o extranjeras
que cotizan en bolsas de EEUU). No cubre empresas privadas, ni empresas
públicas de otros países. Sigue siendo un hueco real para el resto de
jurisdicciones, que hoy no tiene ninguna fuente gratuita equivalente.
"""
import requests
from typing import List, Tuple, Optional

from core.entity_types import Entity
from core.transform_base import Transform, register

HEADERS = {"User-Agent": "RobotEye-OSINT-Tool contacto@sr-robot-labs.com"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"

# Caché a nivel de módulo: el fichero de tickers pesa varios MB y apenas
# cambia -- descargarlo de nuevo en cada nodo Organization de la misma
# sesión sería un desperdicio de red y de tiempo de espera del usuario.
_ticker_cache: Optional[dict] = None


def _get_ticker_map() -> dict:
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache
    resp = requests.get(TICKERS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    _ticker_cache = {str(v["cik_str"]).zfill(10): v["title"] for v in data.values()}
    return _ticker_cache


def _find_cik_by_name(org_name: str) -> Optional[str]:
    """Tres pasadas, de más a menos estricta -- coincidencia exacta
    primero (para no preferir un resultado ambiguo cuando existe uno
    perfecto), luego "el título empieza por el nombre buscado" (cubre
    "Apple" -> "Apple Inc."), y solo como último recurso una subcadena
    cualquiera."""
    ticker_map = _get_ticker_map()
    org_lower = org_name.strip().lower()

    for cik, title in ticker_map.items():
        if title.lower() == org_lower:
            return cik
    for cik, title in ticker_map.items():
        if title.lower().startswith(org_lower):
            return cik
    for cik, title in ticker_map.items():
        if org_lower in title.lower():
            return cik
    return None


def _latest_10k_value(cik: str, concept: str) -> Optional[Tuple[str, float]]:
    """Devuelve (fecha_fin, valor) del dato más reciente de un 10-K para
    ese concepto XBRL, o None si la empresa no reporta ese concepto en
    concreto -- no todas las empresas usan las mismas etiquetas GAAP."""
    resp = requests.get(CONCEPT_URL.format(cik=cik, concept=concept), headers=HEADERS, timeout=15)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    anuales = [d for d in data.get("units", {}).get("USD", []) if d.get("form") == "10-K"]
    if not anuales:
        return None
    anuales.sort(key=lambda d: d["end"], reverse=True)
    return anuales[0]["end"], anuales[0]["val"]


@register
class OrganizationToSECRegistry(Transform):
    name = "Organization → Registro SEC (EDGAR)"
    description = "Registro oficial + financieros básicos -- solo cubre empresas que declaran ante la SEC de EEUU"
    input_types = ["Organization"]

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        cik = _find_cik_by_name(entity.value)
        if cik is None:
            raise RuntimeError(
                f"'{entity.value}' no se encontró en el registro de la SEC de EEUU. "
                "Es lo esperable si no es una empresa pública estadounidense -- SEC "
                "EDGAR no cubre empresas privadas ni de otros países."
            )

        resp = requests.get(SUBMISSIONS_URL.format(cik=cik), headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        props = {
            "sec_razon_social": data.get("name") or "desconocida",
            "sec_cik": str(int(cik)),  # quita ceros a la izquierda sin el riesgo de lstrip()
            "sec_sic": f"{data.get('sic', '?')} ({data.get('sicDescription', 'sin descripción')})",
            "sec_estado_incorporacion": data.get("stateOfIncorporation") or "no reportado",
            "sec_tickers": ", ".join(data.get("tickers", []) or []) or "sin ticker (no cotiza actualmente)",
            "sec_mercados": ", ".join(data.get("exchanges", []) or []) or "ninguno",
        }
        former = data.get("formerNames") or []
        if former:
            props["sec_nombres_anteriores"] = ", ".join(f.get("name", "") for f in former if f.get("name"))

        for concept, etiqueta in [
            ("Revenues", "sec_ingresos_ultimo_10k"),
            ("NetIncomeLoss", "sec_beneficio_neto_ultimo_10k"),
        ]:
            resultado = _latest_10k_value(cik, concept)
            if resultado:
                fecha, valor = resultado
                props[etiqueta] = f"${valor:,.0f} (periodo cerrado {fecha})"

        entity.properties.update(props)
        return []  # enriquecimiento puro -- no genera nodos nuevos
