"""
Al importar este paquete, se cargan todos los módulos de transforms,
lo que dispara los decoradores @register y rellena TRANSFORM_REGISTRY.
"""
from transforms import dns_transforms  # noqa
from transforms import whois_transforms  # noqa
from transforms import crtsh_transforms  # noqa
from transforms import dorking_transforms  # noqa
from transforms import xposedornot_transforms  # noqa
from transforms import phone_transforms  # noqa
from transforms import social_transforms  # noqa
from transforms import wayback_transforms  # noqa
from transforms import metadata_transforms  # noqa
from transforms import asn_transforms  # noqa
from transforms import emailsec_transforms  # noqa
from transforms import username_gen_transforms  # noqa
from transforms import ptr_transforms  # noqa
from transforms import hash_transforms  # noqa
from transforms import shodan_internetdb_transforms  # noqa
from transforms import geolocation_transforms  # noqa
from transforms import pgp_transforms  # noqa
from transforms import webtech_transforms  # noqa
from transforms import organization_transforms  # noqa
from transforms import smtp_verify_transforms  # noqa
from transforms import breach_paste_transforms  # noqa
from transforms import url_transforms  # noqa
from transforms import email_harvest_transforms  # noqa
from transforms import person_enrichment_transforms  # noqa
from transforms import ip_enrichment_transforms  # noqa
from transforms import email_enrichment_transforms  # noqa
from transforms import url_redirect_transforms  # noqa
from transforms import hash_pwned_transforms  # noqa
from transforms import darkweb_transforms  # noqa
from transforms import image_metadata_transforms  # noqa
from transforms import ssl_cert_transforms  # noqa
from transforms import cve_transforms  # noqa
from transforms import mac_vendor_transforms  # noqa
from transforms import public_content_transforms  # noqa
from transforms import email_pivot_transforms  # noqa
from transforms import phone_harvest_transforms  # noqa
from transforms import url_contact_transforms  # noqa
from transforms import sec_edgar_transforms  # noqa
from transforms import ofac_sanctions_transforms  # noqa
from transforms import gdelt_news_transforms  # noqa
from transforms import courtlistener_litigation_transforms  # noqa

from core.transform_base import TRANSFORM_REGISTRY  # noqa
