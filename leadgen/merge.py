"""Dubbels tussen OSM en Google samenvoegen."""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlparse

LEGAL_FORMS = r"\b(bv|bvba|nv|vof|cvba|cv|comm\s?v|srl|sprl|sa|vzw|bvba)\b"


def normalize_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " en ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(LEGAL_FORMS, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = "32" + digits[1:]
    return digits if len(digits) >= 8 else None


def domain(url: str | None) -> str | None:
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host or None


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def name_similarity(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 0.95
    return SequenceMatcher(None, na, nb).ratio()


SOCIAL_DOMAINS = ("facebook.com", "instagram.com", "fb.me", "linktr.ee")


def is_same(a: dict, b: dict) -> bool:
    pa, pb = normalize_phone(a.get("phone")), normalize_phone(b.get("phone"))
    if pa and pb and pa == pb:
        return True
    da, db = domain(a.get("website")), domain(b.get("website"))
    if da and db and da == db and not any(da.endswith(s) for s in SOCIAL_DOMAINS):
        return True
    sim = name_similarity(a["name"], b["name"])
    if a.get("lat") and b.get("lat"):
        dist = haversine_m((a["lat"], a["lon"]), (b["lat"], b["lon"]))
        return (sim >= 0.8 and dist < 300) or (sim >= 0.6 and dist < 60)
    return sim >= 0.92 and (a.get("city") or "").lower() == (b.get("city") or "").lower()


def combine(primary: dict, other: dict) -> dict:
    """Vul lege velden van `primary` aan met die van `other`."""
    out = dict(primary)
    for k, v in other.items():
        if out.get(k) in (None, "", []) and v not in (None, ""):
            out[k] = v
    out["sources"] = set(primary.get("sources") or {primary.get("source")}) | set(
        other.get("sources") or {other.get("source")}
    )
    return out


def merge(leads: list[dict]) -> list[dict]:
    """Google-resultaten eerst (rijkere data), OSM vult aan."""
    ordered = sorted(leads, key=lambda l: 0 if l.get("source") == "places" else 1)
    merged: list[dict] = []
    for lead in ordered:
        lead = {**lead, "sources": set(lead.get("sources") or {lead.get("source")})}
        for i, m in enumerate(merged):
            if (lead.get("place_id") and lead.get("place_id") == m.get("place_id")) or is_same(m, lead):
                merged[i] = combine(m, lead)
                break
        else:
            merged.append(lead)
    for m in merged:
        m["key"] = lead_key(m)
    return merged


def lead_key(lead: dict) -> str:
    if lead.get("place_id"):
        return "g:" + lead["place_id"]
    if lead.get("osm_id"):
        return "osm:" + lead["osm_id"]
    raw = f"{normalize_name(lead['name'])}|{(lead.get('city') or '').lower()}"
    return "h:" + hashlib.sha1(raw.encode()).hexdigest()[:16]
