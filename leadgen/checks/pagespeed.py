"""Mobiele prestatiescore via Google PageSpeed Insights (0-100)."""
from __future__ import annotations

import requests

URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def mobile_score(url: str, api_key: str, timeout: int = 90) -> dict | None:
    params = {"url": url, "strategy": "mobile", "category": "performance"}
    if api_key:
        params["key"] = api_key
    try:
        r = requests.get(URL, params=params, timeout=timeout)
        if r.status_code != 200:
            return None
        lh = r.json().get("lighthouseResult", {})
        score = lh.get("categories", {}).get("performance", {}).get("score")
        audits = lh.get("audits", {})
        return {
            "score": round(score * 100) if score is not None else None,
            "lcp": audits.get("largest-contentful-paint", {}).get("displayValue"),
        }
    except (requests.RequestException, ValueError):
        return None
