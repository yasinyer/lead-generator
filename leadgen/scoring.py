"""Lead-score 0-100 = nood aan een site (max 60) + 'draait goed / heeft budget' (max 40)."""
from __future__ import annotations

ISSUE_WEIGHTS = {
    "no_viewport": 25,
    "overflow": 25,
    "small_text": 12,
    "no_https": 10,
    "ssl_error": 12,
    "old_copyright": 8,
    "flash": 15,
    "frames": 15,
    "old_html": 12,
    "old_cms": 10,
    "thin": 8,
    "builder": 15,
    "slow": 12,
    "meh_speed": 6,
    "no_title": 3,
    "no_description": 2,
}
MOBILE_CODES = {"no_viewport", "overflow", "small_text"}

STATUS_NEED = {
    "none": 60,
    "social": 58,
    "directory": 56,
    "offline": 55,
    "placeholder": 55,
    # Geen website in OpenStreetMap, maar niet bevestigd door Google: vaak hebben ze er wel één.
    "unverified": 25,
}

WEB_STATUS_LABELS = {
    "none": "Geen website",
    "unverified": "Website onbekend",
    "social": "Alleen social media",
    "directory": "Alleen gids/boekingsplatform",
    "offline": "Site kapot/offline",
    "placeholder": "Placeholder-pagina",
    "builder": "Gratis sitebouwer",
    "weak": "Zwakke site",
    "ok": "Site oké",
    "unknown": "Onbekend",
}


def need_score(web_status: str, issues: list[dict]) -> int:
    if web_status in STATUS_NEED:
        return STATUS_NEED[web_status]
    codes = {i["code"] for i in issues}
    mobile = min(30, sum(ISSUE_WEIGHTS[c] for c in codes & MOBILE_CODES))
    other = sum(ISSUE_WEIGHTS.get(c, 0) for c in codes - MOBILE_CODES)
    return min(50, mobile + other)


def budget_score(rating: float | None, reviews: int | None) -> int:
    if rating is None:
        r = 5
    elif rating >= 4.5:
        r = 15
    elif rating >= 4.2:
        r = 12
    elif rating >= 3.8:
        r = 8
    elif rating >= 3.0:
        r = 3
    else:
        r = 0
    if reviews is None:
        n = 5
    elif reviews >= 150:
        n = 20
    elif reviews >= 75:
        n = 17
    elif reviews >= 30:
        n = 13
    elif reviews >= 10:
        n = 8
    elif reviews >= 3:
        n = 4
    else:
        n = 1
    return r + n


def score_lead(lead: dict) -> int:
    s = need_score(lead.get("web_status") or "unknown", lead.get("issues") or [])
    s += budget_score(lead.get("rating"), lead.get("review_count"))
    if lead.get("phone"):
        s += 3
    if lead.get("email"):
        s += 2
    return max(0, min(100, s))


def classify_site(issues: list[dict]) -> str:
    """Voor een bereikbare eigen site: 'weak' of 'ok'."""
    return "weak" if need_score("site", issues) >= 15 else "ok"
