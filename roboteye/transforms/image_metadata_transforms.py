"""
`URL → Metadatos de imagen (EXIF)`: extrae los metadatos EXIF incrustados
en fotografías -- coordenadas GPS de dónde se tomó la foto, modelo de
cámara/móvil, fecha y hora exactas. Es la técnica de geolocalización por
fotografía más clásica de OSINT/periodismo de investigación: mucha gente
sube fotos sin saber que llevan la ubicación exacta incrustada (o creyendo
que la red social se la ha quitado, cosa que muchas SÍ hacen -- ver aviso
de cobertura más abajo).

Mismo patrón que `URL → Metadatos del documento`: se descarga la imagen
con una petición HTTP normal (lo mismo que hace un navegador al mostrarla),
no se sondea ni se ataca nada. Reutiliza el mismo límite de tamaño de
descarga ya establecido para documentos (`_download_with_size_cap`).

Aviso de cobertura honesto:
  - JPEG y TIFF llevan EXIF de forma nativa y fiable -- son los formatos
    que cubre esta transform.
  - PNG y WEBP casi nunca lo llevan (la inmensa mayoría de herramientas
    que los generan no lo incluyen), así que no se ofrecen aquí -- evita
    prometer una comprobación que en la práctica case siempre da vacío.
  - Las redes sociales grandes (Facebook, Instagram, Twitter/X, WhatsApp)
    **eliminan el EXIF, incluido el GPS, al volver a comprimir las fotos
    que subes** -- por eso esta transform casi nunca encontrará GPS en una
    foto bajada de esas plataformas. Sí es habitual encontrarlo en fotos
    alojadas directamente en la web propia de alguien, en foros que no
    recomprimen, o en documentos/PDFs con fotos incrustadas sin procesar.
"""
import io
from typing import List, Tuple, Optional
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from core.entity_types import Entity
from core.transform_base import Transform, register
from transforms.metadata_transforms import _download_with_size_cap

SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".tiff", ".tif")
GPS_IFD_TAG = 0x8825


def _dms_to_decimal(dms, ref) -> float:
    degrees, minutes, seconds = (float(v) for v in dms)
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def _extract_gps_decimal(gps_ifd: dict) -> Optional[Tuple[float, float]]:
    named = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
    lat, lat_ref = named.get("GPSLatitude"), named.get("GPSLatitudeRef")
    lon, lon_ref = named.get("GPSLongitude"), named.get("GPSLongitudeRef")
    if not (lat and lat_ref and lon and lon_ref):
        return None
    return _dms_to_decimal(lat, lat_ref), _dms_to_decimal(lon, lon_ref)


@register
class URLToImageMetadata(Transform):
    name = "URL → Metadatos de imagen (EXIF)"
    description = "Extrae GPS, cámara y fecha de una foto pública -- muchas llevan la ubicación exacta incrustada sin que el autor lo sepa"
    input_types = ["URL"]

    def applies_to(self, entity: Entity) -> bool:
        if entity.type != "URL":
            return False
        lower = entity.value.lower().split("?")[0].split("#")[0]
        return lower.endswith(SUPPORTED_IMAGE_EXTENSIONS)

    def run(self, entity: Entity) -> List[Tuple[Entity, str]]:
        data = _download_with_size_cap(entity.value, label="la imagen")

        try:
            img = Image.open(io.BytesIO(data))
            exif = img.getexif()
        except Exception as ex:
            raise RuntimeError(f"No se pudo abrir la imagen o su EXIF está corrupto: {ex}")

        if not exif:
            entity.properties["exif"] = (
                "sin metadatos EXIF -- la imagen no lleva ninguno, o se eliminaron "
                "antes de publicarla (habitual al subir fotos a redes sociales grandes)"
            )
            return []

        named = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif.items()}

        entity.properties["camara_fabricante"] = str(named.get("Make", "no revelado"))
        entity.properties["camara_modelo"] = str(named.get("Model", "no revelado"))
        entity.properties["fecha_captura"] = str(
            named.get("DateTimeOriginal") or named.get("DateTime") or "no revelada"
        )
        if named.get("Software"):
            entity.properties["software_edicion"] = str(named["Software"])

        gps_ifd = exif.get_ifd(GPS_IFD_TAG)
        if not gps_ifd:
            entity.properties["gps_coordenadas"] = "sin datos GPS en esta imagen"
            return []

        coords = _extract_gps_decimal(gps_ifd)
        if not coords:
            entity.properties["gps_coordenadas"] = "presentes pero incompletos, no se pudo calcular la posición"
            return []

        lat, lon = coords
        entity.properties["gps_coordenadas"] = f"{lat:.6f}, {lon:.6f}"
        entity.properties["gps_google_maps"] = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
        return []
