"""OpenStreetMap via de Overpass API: gratis, geen key nodig, wel minder volledig."""
from __future__ import annotations

import time

import requests

from .. import config

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


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
    return f"[out:json][timeout:90];\n{area_def}\n(\n{parts}\n);\nout center tags;"


def run_query(query: str, log=print) -> list[dict]:
    last_err = None
    for url in OVERPASS_URLS:
        for attempt in range(2):
            try:
                r = requests.post(url, data={"data": query}, timeout=(10, 120),
                                  headers={"User-Agent": "lead-generator/1.0"})
                if r.status_code in (429, 504):
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r.json().get("elements", [])
            except (requests.RequestException, ValueError) as e:
                last_err = e
                log(f"  OSM-server {url.split('/')[2]} antwoordt niet, ik probeer een andere...")
                break
    log(f"  ! OSM/Overpass niet bereikbaar: {last_err}")
    return []


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
           province: bool = False, log=print) -> list[dict]:
    tags = config.SECTORS[sector]["osm"]
    if province:
        query = build_query(tags, province=True)
    else:
        lat, lon = config.CITIES[city]
        query = build_query(tags, around=(lat, lon, radius))
    results = []
    for el in run_query(query, log=log):
        lead = parse_element(el, sector=sector, fallback_city=city)
        if lead and not lead["disused"]:
            results.append(lead)
    return results
