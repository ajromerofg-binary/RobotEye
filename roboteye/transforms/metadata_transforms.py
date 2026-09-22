"""
Transform de extracción de metadatos de documentos -- la técnica clásica de
FOCA/Metagoofil: los documentos ofimáticos públicos (PDF, DOCX, XLSX) llevan
metadatos incrustados por el software que los generó -- autor, usuario que
hizo la última edición, empresa, software y versión usados, fechas de
creación/modificación. Cruzando esto entre muchos documentos de una misma
organización se pueden sacar nombres de usuario internos reales, que
además encajan directamente con las transforms de Username ya existentes.

Cierra el círculo con el diseño original del proyecto: el Google Dorking
(`Domain → Google Dorks` → `Ejecutar Dork`) ya genera precisamente URLs de
PDFs/DOCX/XLSX públicos -- esta transform es el siguiente paso natural
sobre esos resultados.

Sigue siendo OSINT pasivo: se descarga un documento público con una
petición HTTP normal (lo mismo que hace un navegador), no se sondea ni se
ataca ninguna infraestructura.
"""
import io
import zipfile
from xml.etree import ElementTree as ET
from typing import List, Tuple, Optional
import requests
import pypdf
import docx
import openpyxl

from core.entity_types import Entity
from core.transform_base import Transform, register


MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20 MB, para no descargar ficheros enormes
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".xlsx")

# DOCX y XLSX son en realidad ficheros ZIP con varias partes XML dentro. El
# campo "Company" vive en docProps/app.xml (Extended Properties) -- una
# parte que ni python-docx ni openpyxl exponen en su API de alto nivel (solo
# exponen docProps/core.xml: autor, fechas, título...). Como es justo uno de
# los datos más valiosos para OSINT, lo leemos directamente del XML interno.
APP_PROPS_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"


def _extract_ooxml_company(data: bytes) -> Optional[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "docProps/app.xml" not in z.namelist():
                return None
            xml_data = z.read("docProps/app.xml")
        root = ET.fromstring(xml_data)
        company_el = root.find(f"{APP_PROPS_NS}Company")
        if company_el is not None and company_el.text and company_el.text.strip():
            return company_el.text.strip()
    except Exception:
        pass  # si el XML interno viene raro, simplemente no sacamos el dato -- no es crítico
    return None


def _download_with_size_cap(url: str, label: str = "el documento") -> bytes:
    resp = requests.get(url, stream=True, timeout=20, headers={"User-Agent": "RobotEye-OSINT-Tool"})
    resp.raise_for_status()

    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError(
            f"{label.capitalize()} pesa {int(content_length) / 1_000_000:.1f} MB, por encima "
            f"del límite de {MAX_DOWNLOAD_BYTES / 1_000_000:.0f} MB. No se descarga."
        )

    chunks = []
    total = 0
    for chunk in resp.iter_content(chunk_size=65536):
        total += len(chunk)
        if total > MAX_DOWNLOAD_BYTES:
            raise RuntimeError(f"{label.capitalize()} supera el límite de {MAX_DOWNLOAD_BYTES / 1_000_000:.0f} MB. No se descarga.")
        chunks.append(chunk)
    return b"".join(chunks)


def _extract_pdf_metadata(data: bytes) -> dict:
    reader = pypdf.PdfReader(io.BytesIO(data))
    meta = reader.metadata or {}
    return {
        "autor": meta.get("/Author"),
        "creador_software": meta.get("/Creator"),
        "productor_software": meta.get("/Producer"),
        "titulo": meta.get("/Title"),
        "asunto": meta.get("/Subject"),
        "fecha_creacion": str(meta.get("/CreationDate")) if meta.get("/CreationDate") else None,
        "fecha_modificacion": str(meta.get("/ModDate")) if meta.get("/ModDate") else None,
        "num_paginas": len(reader.pages),
    }


def _extract_docx_metadata(data: bytes) -> dict:
    document = docx.Document(io.BytesIO(data))
    props = document.core_properties
    return {
        "autor": props.author,
        "ultima_modificacion_por": props.last_modified_by,
        "empresa": _extract_ooxml_company(data),
        "titulo": props.title,
        "asunto": props.subject,
        "fecha_creacion": str(props.created) if props.created else None,
        "fecha_modificacion": str(props.modified) if props.modified else None,
        "revision": props.revision,
    }


def _extract_xlsx_metadata(data: bytes) -> dict:
    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
    props = workbook.properties
    return {
        "autor": props.creator,
        "ultima_modificacion_por": props.lastModifiedBy,
        "empresa": _extract_ooxml_company(data),
        "titulo": props.title,
        "asunto": props.subject,
        "fecha_creacion": str(props.created) if props.created else None,
        "fecha_modificacion": str(props.modified) if props.modified else None,
    }


@register
class URLToDocumentMetadata(Transform):
    name = "URL → Metadatos del documento (PDF/DOCX/XLSX)"
    description = "Descarga el documento público y extrae autor, software y fechas (técnica FOCA)"
    input_types = ["URL"]

    def applies_to(self, entity: Entity) -> bool:
        if entity.type != "URL":
            return False
        # Hay que quitar tanto el query string (?) como el fragmento (#)
        # antes de mirar la extensión -- una URL real como
        # "https://x.com/doc.pdf#section1" es un PDF igualmente.
        url_lower = entity.value.lower().split("?")[0].split("#")[0]
        return any(url_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS)

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        url_lower = entity.value.lower().split("?")[0]  # ignoramos query string para mirar la extensión
        matching_ext = next((ext for ext in SUPPORTED_EXTENSIONS if url_lower.endswith(ext)), None)
        if matching_ext is None:
            raise RuntimeError(
                f"'{entity.value}' no parece un PDF, DOCX o XLSX (por la extensión de la URL). "
                "Esta transform solo soporta esos tres formatos."
            )

        data = _download_with_size_cap(entity.value)

        try:
            if matching_ext == ".pdf":
                metadata = _extract_pdf_metadata(data)
            elif matching_ext == ".docx":
                metadata = _extract_docx_metadata(data)
            else:  # .xlsx
                metadata = _extract_xlsx_metadata(data)
        except Exception as ex:
            raise RuntimeError(f"No se pudo leer el documento (¿corrupto o no es realmente {matching_ext}?): {ex}")

        # Guardamos todos los metadatos encontrados en el propio nodo URL
        entity.properties.update({k: v for k, v in metadata.items() if v})

        results = []
        autor = metadata.get("autor")
        if autor and autor.strip():
            results.append((Entity(type="Person", value=autor.strip()), "autor del documento"))

        ultima_mod = metadata.get("ultima_modificacion_por")
        if ultima_mod and ultima_mod.strip() and ultima_mod.strip() != (autor or "").strip():
            results.append((Entity(type="Person", value=ultima_mod.strip()), "última modificación del documento"))

        empresa = metadata.get("empresa")
        if empresa and empresa.strip():
            results.append((Entity(type="Organization", value=empresa.strip()), "empresa (metadatos del documento)"))

        return results
