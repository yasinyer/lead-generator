"""Instellingen: sectoren, steden en API-keys.

Pas sectoren/steden gerust aan. Keys en je eigen gegevens stel je in via
het dashboard (knop "Instellingen"), dat ze in `.env` bewaart.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# In de Mac-app (PyInstaller) staat de code in de app zelf; gegevens horen daarbuiten,
# zodat ze een update van de app overleven.
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    USER_DIR = (Path.home() / "Library" / "Application Support" / "Lead Generator"
                if sys.platform == "darwin" else Path.home() / ".leadgen")
else:
    USER_DIR = BASE_DIR
ENV_PATH = Path(os.environ.get("LEADGEN_ENV", USER_DIR / ".env"))
LOG_PATH = USER_DIR / "leadgen.log"

try:  # python-dotenv is optioneel
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)
except ImportError:  # pragma: no cover
    pass
DATA_DIR = Path(os.environ.get("LEADGEN_DATA_DIR", USER_DIR / "data"))
DB_PATH = Path(os.environ.get("LEADGEN_DB", DATA_DIR / "leads.db"))
SCREENSHOT_DIR = DATA_DIR / "screenshots"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
# PageSpeed Insights kan dezelfde key gebruiken (zet de API aan in hetzelfde project).
PAGESPEED_API_KEY = os.environ.get("PAGESPEED_API_KEY", "").strip() or GOOGLE_API_KEY

# Maximaal aantal Places API-calls per scan (beschermt je gratis quotum).
PLACES_MAX_CALLS = int(os.environ.get("PLACES_MAX_CALLS", "150"))

# Jouw gegevens, gebruikt in de pitch-tekst in het dashboard.
DESIGNER_NAME = os.environ.get("DESIGNER_NAME", "")
DESIGNER_CITY = os.environ.get("DESIGNER_CITY", "Hasselt")
DESIGNER_PHONE = os.environ.get("DESIGNER_PHONE", "")
DESIGNER_EMAIL = os.environ.get("DESIGNER_EMAIL", "")
DESIGNER_WEBSITE = os.environ.get("DESIGNER_WEBSITE", "")
PRICE_ONEPAGER = os.environ.get("PRICE_ONEPAGER", "1.200")
PRICE_MULTIPAGE = os.environ.get("PRICE_MULTIPAGE", "2.000 à 2.500")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

# sleutel -> label, zoekterm voor Google en OSM-tags (key=value)
SECTORS: dict[str, dict] = {
    "kapper": {
        "label": "Kappers",
        "query": "kapper",
        "osm": ["shop=hairdresser"],
    },
    "schoonheid": {
        "label": "Schoonheidssalons",
        "query": "schoonheidssalon",
        "osm": ["shop=beauty"],
    },
    "kinesist": {
        "label": "Kinesisten",
        "query": "kinesist",
        "osm": ["healthcare=physiotherapist", "amenity=physiotherapist"],
    },
    "aannemer": {
        "label": "Aannemers",
        "query": "aannemer",
        "osm": [
            "craft=builder",
            "craft=roofer",
            "craft=tiler",
            "craft=carpenter",
            "craft=plasterer",
            "craft=painter",
            "office=construction_company",
        ],
    },
    "schoonmaak": {
        "label": "Schoonmaakbedrijven",
        "query": "schoonmaakbedrijf",
        "osm": ["craft=cleaning", "office=cleaning"],
    },
    "restaurant": {
        "label": "Restaurants",
        "query": "restaurant",
        "osm": ["amenity=restaurant"],
    },
    "garage": {
        "label": "Garages",
        "query": "garage autoherstelling",
        "osm": ["shop=car_repair", "shop=tyres"],
    },
    "frituur": {
        "label": "Frituren",
        "query": "frituur",
        "osm": ["cuisine=friture"],
    },
    "bakker": {
        "label": "Bakkers",
        "query": "bakker",
        "osm": ["shop=bakery"],
    },
}

# Limburgse gemeenten met (ongeveer) hun centrum: (lat, lon)
CITIES: dict[str, tuple[float, float]] = {
    "Hasselt": (50.9307, 5.3378),
    "Genk": (50.9650, 5.5008),
    "Sint-Truiden": (50.8167, 5.1864),
    "Tongeren": (50.7806, 5.4647),
    "Beringen": (51.0494, 5.2261),
    "Lommel": (51.2306, 5.3131),
    "Maasmechelen": (50.9653, 5.6944),
    "Bilzen": (50.8728, 5.5186),
    "Lanaken": (50.8931, 5.6475),
    "Heusden-Zolder": (51.0317, 5.3125),
    "Houthalen-Helchteren": (51.0333, 5.3833),
    "Diepenbeek": (50.9078, 5.4189),
    "Zonhoven": (50.9911, 5.3681),
    "Maaseik": (51.0981, 5.7836),
    "Bree": (51.1414, 5.5967),
    "Pelt": (51.2208, 5.4222),
    "Peer": (51.1306, 5.4594),
    "Leopoldsburg": (51.1167, 5.2575),
    "Herk-de-Stad": (50.9397, 5.1672),
    "Lummen": (50.9872, 5.1914),
    "Tessenderlo-Ham": (51.0650, 5.0886),
    "Alken": (50.8750, 5.3053),
    "Kortessem": (50.8594, 5.3889),
    "Riemst": (50.8094, 5.6000),
    "Dilsen-Stokkem": (51.0286, 5.7208),
    "Oudsbergen": (51.0560, 5.5600),
    "Hamont-Achel": (51.2500, 5.5500),
    "Halen": (50.9483, 5.1114),
    "Nieuwerkerken": (50.8636, 5.1931),
    "Wellen": (50.8414, 5.3394),
    "Borgloon": (50.8028, 5.3436),
    "As": (51.0081, 5.5847),
    "Zutendaal": (50.9325, 5.5747),
    "Hechtel-Eksel": (51.1250, 5.3700),
    "Kinrooi": (51.1456, 5.7461),
    "Voeren": (50.7564, 5.7883),
}

DEFAULT_RADIUS_M = 5000

STATUSES: list[tuple[str, str]] = [
    ("nieuw", "Nieuw"),
    ("interessant", "Interessant"),
    ("mockup", "Mockup gemaakt"),
    ("gecontacteerd", "Gecontacteerd"),
    ("opvolgen", "Opvolgen"),
    ("klant", "Klant 🎉"),
    ("afgewezen", "Afgewezen"),
    ("niet_relevant", "Niet relevant"),
]


# ---------- instellingen bewaren vanuit het dashboard ----------
# naam in .env -> (attribuut in deze module, type)
SETTINGS = {
    "GOOGLE_API_KEY": ("GOOGLE_API_KEY", str),
    "PLACES_MAX_CALLS": ("PLACES_MAX_CALLS", int),
    "DESIGNER_NAME": ("DESIGNER_NAME", str),
    "DESIGNER_CITY": ("DESIGNER_CITY", str),
    "DESIGNER_PHONE": ("DESIGNER_PHONE", str),
    "DESIGNER_EMAIL": ("DESIGNER_EMAIL", str),
    "DESIGNER_WEBSITE": ("DESIGNER_WEBSITE", str),
    "PRICE_ONEPAGER": ("PRICE_ONEPAGER", str),
    "PRICE_MULTIPAGE": ("PRICE_MULTIPAGE", str),
}
SECRET_SETTINGS = {"GOOGLE_API_KEY"}


def current_settings() -> dict:
    """Voor het dashboard. Geheime waarden worden nooit volledig teruggestuurd."""
    out = {}
    mod = sys.modules[__name__]
    for name, (attr, _) in SETTINGS.items():
        val = getattr(mod, attr)
        if name in SECRET_SETTINGS:
            out[name] = {"set": bool(val), "hint": f"••••{val[-4:]}" if val else ""}
        else:
            out[name] = val
    return out


def _quote(v: str) -> str:
    v = str(v).replace("\r", " ").replace("\n", " ").strip()
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_settings(values: dict, env_path: Path | None = None) -> None:
    """Werk .env bij (andere regels blijven staan) en pas de waarden meteen toe."""
    global PAGESPEED_API_KEY
    env_path = Path(env_path or ENV_PATH)
    mod = sys.modules[__name__]
    clean: dict[str, str] = {}
    for name, raw in values.items():
        if name not in SETTINGS or raw is None:
            continue
        attr, typ = SETTINGS[name]
        if typ is int:
            setattr(mod, attr, int(raw))
        else:
            setattr(mod, attr, str(raw).strip())
        clean[name] = str(getattr(mod, attr))
    if "GOOGLE_API_KEY" in clean:
        PAGESPEED_API_KEY = os.environ.get("PAGESPEED_API_KEY", "").strip() or GOOGLE_API_KEY

    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    done = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in clean and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={_quote(clean[key])}"
            done.add(key)
    lines += [f"{k}={_quote(v)}" for k, v in clean.items() if k not in done]
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
