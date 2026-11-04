"""OpenStreetMap via de Overpass API: gratis, geen key nodig, wel minder volledig."""
from __future__ import annotations

import time

import requests

from .. import config

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
# Servers die in deze sessie al faalden, komen achteraan (sneller bij volgende zoekopdrachten).
_bad: list[str] = []


def _tag_filter(tag: str) -> str:
    k, v = tag.split("=", 1)
    return f'["{k}"="{v}"]'


def build_query(osm_tags: list[str], *, around: tuple[float, float, int] | None = None,
                province: bool = False) -> str:
    if province:
        area_def = 'area["ISO3166-2"="BE-VLI"]->.a;'
        scope = "(area.a)"
    elif around:
        lat, lon, radius = around
        area_def = ""
        scope = f"(around:{radius},{lat},{lon})"
    else:
        raise ValueError("geef 'around' of 'province' op")
    parts = "\n".join(f"  nwr{_tag_filter(t)}[\"name\"]{scope};" for t in osm_tags)
    timeout = 180 if province else 60
    return f"[out:json][timeout:{timeout}];\n{area_def}\n(\n{parts}\n);\nout center tags;"


def _why(e: Exception) -> str:
    if isinstance(e, requests.Timeout):
        return "time-out"
    if isinstance(e, requests.HTTPError) and e.response is not None:
        return f"foutcode {e.response.status_code}"
    if isinstance(e, requests.ConnectionError):
        return "geen verbinding"
    return e.__class__.__name__


def run_query(query: str, log=print, *, read_timeout: int = 120) -> list[dict] | None:
    """Elementen van een Overpass-query, of None als geen enkele server antwoordt."""
    servers = [u for u in OVERPASS_URLS if u not in _bad] + [u for u in _bad]
    for url in servers:
        host = url.split("/")[2]
        for attempt in range(2):
            try:
                r = requests.post(url, data={"data": query}, timeout=(10, read_timeout),
                                  headers={"User-Agent": "lead-generator/1.0"})
                if r.status_code in (429, 504) and attempt == 0:
                    log(f"  OSM-server {host} is druk, ik wacht even...")
                    time.sleep(8)
                    continue
                r.raise_for_status()
                elements = r.json().get("elements", [])
                if url in _bad:
                    _bad.remove(url)
                return elements
            except (requests.RequestException, ValueError) as e:
                log(f"  OSM-server {host} antwoordt niet ({_why(e)}), ik probeer een andere...")
                if url not in _bad:
                    _bad.append(url)
                break
    log("  ! Geen enkele OSM-server antwoordt. Probeer het later opnieuw, of zoek per gemeente.")
    return None


def _first(tags: dict, *keys: str) -> str | None:
    for k in keys:
        v = tags.get(k)
        if v:
            return v.split(";")[0].strip()
    return None


def parse_element(el: dict, *, sector: str, fallback_city: str | None) -> dict | None:
    tags = el.get("tags") or {}
    name = tags.get("name")
    if not name:
        return None
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    street = " ".join(x for x in [tags.get("addr:street"), tags.get("addr:housenumber")] if x)
    city = tags.get("addr:city") or fallback_city
    locality = " ".join(x for x in [tags.get("addr:postcode"), tags.get("addr:city")] if x)
    address = ", ".join(x for x in [street, locality] if x) or None

    website = _first(tags, "website", "contact:website", "url")
    facebook = _first(tags, "contact:facebook", "facebook")
    if website and "facebook.com" in website and not facebook:
        facebook = website
    return {
        "source": "osm",
        "osm_id": f"{el.get('type')}/{el.get('id')}",
        "name": name.strip(),
        "sector": sector,
        "city": city,
        "address": address,
        "phone": _first(tags, "phone", "contact:phone", "contact:mobile", "mobile"),
        "email": _first(tags, "email", "contact:email"),
        "website": website,
        "facebook": facebook,
        "lat": lat,
        "lon": lon,
        "rating": None,
        "review_count": None,
        "disused": any(k.startswith(("disused:", "was:")) for k in tags),
    }


def search(sector: str, *, city: str | None = None, radius: int = config.DEFAULT_RADIUS_M,
           province: bool = False, log=print) -> list[dict] | None:
    """Zaken van één sector, of None als OpenStreetMap niet bereikbaar was."""
    tags = config.SECTORS[sector]["osm"]
    if province:
        elements = run_query(build_query(tags, province=True), log=log, read_timeout=200)
    else:
        lat, lon = config.CITIES[city]
        elements = run_query(build_query(tags, around=(lat, lon, radius)), log=log)
    if elements is None:
        return None
    results = []
    for el in elements:
        lead = parse_element(el, sector=sector, fallback_city=city)
        if lead and not lead["disused"]:
            results.append(lead)
    return results
