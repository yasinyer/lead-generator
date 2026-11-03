"""Google Places API (New): Text Search voor reviews, rating, telefoon en website."""
from __future__ import annotations

import requests

from .. import config

URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.addressComponents",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.googleMapsUri",
    "places.location",
    "places.businessStatus",
    "nextPageToken",
])


class Budget:
    """Telt API-calls zodat je niet ongemerkt door je gratis quotum gaat."""

    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.used = 0

    def take(self) -> bool:
        if self.used >= self.max_calls:
            return False
        self.used += 1
        return True


class PlacesClient:
    def __init__(self, api_key: str, budget: Budget, log=print):
        self.api_key = api_key
        self.budget = budget
        self.log = log
        self.session = requests.Session()

    def _post(self, body: dict) -> dict | None:
        if not self.budget.take():
            return None
        r = self.session.post(URL, json=body, timeout=30, headers={
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        })
        if r.status_code != 200:
            try:
                msg = r.json().get("error", {}).get("message", r.text[:200])
            except ValueError:
                msg = r.text[:200]
            self.log(f"  ! Places API fout {r.status_code}: {msg}")
            return None
        return r.json()

    def text_search(self, text: str, *, center: tuple[float, float] | None = None,
                    radius: float = config.DEFAULT_RADIUS_M, max_pages: int = 3,
                    page_size: int = 20) -> list[dict]:
        body: dict = {"textQuery": text, "languageCode": "nl", "regionCode": "BE",
                      "pageSize": page_size}
        if center:
            body["locationBias"] = {"circle": {
                "center": {"latitude": center[0], "longitude": center[1]},
                "radius": float(min(radius, 50000)),
            }}
        places: list[dict] = []
        for _ in range(max_pages):
            data = self._post(body)
            if not data:
                break
            places += data.get("places", [])
            token = data.get("nextPageToken")
            if not token:
                break
            body["pageToken"] = token
        return places


def _city_from_components(components: list[dict] | None) -> str | None:
    for c in components or []:
        if "locality" in c.get("types", []):
            return c.get("longText")
    return None


def parse_place(p: dict, *, sector: str, fallback_city: str | None) -> dict:
    loc = p.get("location") or {}
    return {
        "source": "places",
        "place_id": p.get("id"),
        "name": (p.get("displayName") or {}).get("text", "").strip(),
        "sector": sector,
        "city": _city_from_components(p.get("addressComponents")) or fallback_city,
        "address": p.get("formattedAddress"),
        "phone": p.get("nationalPhoneNumber"),
        "email": None,
        "website": p.get("websiteUri"),
        "facebook": None,
        "lat": loc.get("latitude"),
        "lon": loc.get("longitude"),
        "rating": p.get("rating"),
        "review_count": p.get("userRatingCount"),
        "maps_url": p.get("googleMapsUri"),
        "business_status": p.get("businessStatus"),
    }


def search(client: PlacesClient, sector: str, city: str, *,
           radius: int = config.DEFAULT_RADIUS_M, max_pages: int = 3) -> list[dict]:
    query = f"{config.SECTORS[sector]['query']} in {city}"
    places = client.text_search(query, center=config.CITIES.get(city), radius=radius,
                                max_pages=max_pages)
    return [parse_place(p, sector=sector, fallback_city=city) for p in places]


def lookup(client: PlacesClient, name: str, city: str | None,
           lat: float | None, lon: float | None) -> dict | None:
    """Zoek één OSM-zaak op in Google om reviews/rating aan te vullen."""
    text = f"{name} {city or ''}".strip()
    center = (lat, lon) if lat and lon else None
    res = client.text_search(text, center=center, radius=500, max_pages=1, page_size=1)
    return res[0] if res else None
