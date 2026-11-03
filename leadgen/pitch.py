"""Gepersonaliseerde eerste boodschap op basis van wat er mis is met hun online aanwezigheid."""
from __future__ import annotations

from . import config
from .merge import domain

PRIORITY = ["overflow", "no_viewport", "small_text", "ssl_error", "no_https", "slow",
            "old_copyright", "flash", "frames", "old_html", "old_cms", "thin", "meh_speed"]

FRIENDLY = {
    "overflow": "op een gsm moet je zijwaarts scrollen om alles te zien",
    "no_viewport": "de site past zich niet aan op een gsm-scherm",
    "small_text": "de tekst is op gsm erg klein",
    "ssl_error": "browsers tonen een waarschuwing over het beveiligingscertificaat",
    "no_https": "browsers tonen 'Niet veilig' naast jullie adres",
    "slow": "de site laadt traag op mobiel",
    "meh_speed": "de site kan sneller laden op mobiel",
    "old_copyright": "de site lijkt al een tijd niet meer bijgewerkt",
    "flash": "er wordt Flash gebruikt, dat werkt in geen enkele browser meer",
    "frames": "de site gebruikt een verouderde techniek (frames)",
    "old_html": "de opbouw van de site is technisch verouderd",
    "old_cms": "de site draait op een verouderd systeem",
    "thin": "er staat weinig informatie op de homepage",
}


def _fmt_rating(r: float) -> str:
    return f"{r:.1f}".replace(".", ",")


def make_pitch(lead: dict) -> dict:
    name = lead.get("name", "")
    rating, reviews = lead.get("rating"), lead.get("review_count")
    good_reviews = rating and reviews and rating >= 4.0 and reviews >= 10
    status = lead.get("web_status")
    codes = [i["code"] for i in lead.get("issues") or []]

    me = config.DESIGNER_NAME or "[jouw naam]"
    intro = f"Hallo,\n\nIk ben {me}, webdesigner uit {config.DESIGNER_CITY}."
    compliment = (
        f" Ik zag op Google dat jullie {_fmt_rating(rating)} sterren hebben uit {reviews} reviews, "
        "jullie klanten zijn duidelijk tevreden."
        if good_reviews else ""
    )

    if status == "none":
        obs = f"{compliment} Wat me opviel: jullie hebben nog geen eigen website."
        subject = f"Een website voor {name}?"
    elif status == "social":
        obs = (f"{compliment} Ik merkte dat jullie online vooral via Facebook/Instagram te vinden zijn. "
               "Wie jullie op Google zoekt, vindt zo geen eigen site met jullie diensten, "
               "openingsuren en contactgegevens.")
        subject = f"Een eigen website voor {name}"
    elif status == "directory":
        obs = (f"{compliment} Ik merkte dat jullie online enkel via "
               f"{domain(lead.get('website')) or 'een gids'} te vinden zijn, niet via een eigen website.")
        subject = f"Een eigen website voor {name}"
    elif status == "offline":
        obs = f"{compliment} Ik wilde jullie website bekijken, maar die werkt momenteel niet."
        subject = f"Jullie website ({domain(lead.get('website'))}) werkt niet"
    elif status == "placeholder":
        obs = f"{compliment} Op jullie domeinnaam staat nu enkel een tijdelijke pagina."
        subject = f"Jullie website {domain(lead.get('website'))}"
    else:
        points = [FRIENDLY[c] for c in PRIORITY if c in codes][:3]
        if status == "builder":
            points.insert(0, "het webadres is dat van een gratis sitebouwer, wat minder professioneel overkomt")
        bullet = "\n".join(f"- {p}" for p in points) or "- er is nog ruimte voor verbetering"
        obs = (f"{compliment} Ik bekeek jullie website op mijn gsm en zag een paar dingen "
               f"die klanten kunnen afschrikken:\n{bullet}")
        subject = "Een paar dingen die me opvielen aan jullie website"

    body = (
        f"{intro}{obs}\n\n"
        "Ik heb alvast een voorbeeld gemaakt van hoe jullie homepage eruit zou kunnen zien "
        "(zie bijlage). Helemaal vrijblijvend, gewoon om te tonen wat mogelijk is.\n\n"
        f"Ik werk met een vast pakket: een professionele one-pager, mobile-first, klaar in 7 dagen "
        f"voor €{config.PRICE_ONEPAGER}. Hosting en onderhoud kan ik er maandelijks bij nemen, "
        "zodat jullie er geen omkijken naar hebben.\n\n"
        "Zin om er even over te bellen of af te spreken?\n\n"
        f"Groeten,\n{me}"
    )
    for extra in (config.DESIGNER_PHONE, config.DESIGNER_EMAIL, config.DESIGNER_WEBSITE):
        if extra:
            body += f"\n{extra}"
    body += "\n\nP.S. Liever geen berichten meer van mij? Laat het gerust weten, dan stop ik."

    call = (
        f"Goeiedag, u spreekt met {me}, webdesigner uit {config.DESIGNER_CITY}. "
        f"Ik bel even omdat ik {'jullie mooie reviews zag, maar ' if good_reviews else ''}"
        + {
            "none": "merkte dat jullie nog geen website hebben.",
            "social": "zag dat jullie online vooral via Facebook te vinden zijn.",
            "directory": "zag dat jullie geen eigen website hebben.",
            "offline": "merkte dat jullie website niet meer werkt.",
            "placeholder": "zag dat er op jullie domein nog geen echte site staat.",
        }.get(status, "jullie website op mijn gsm bekeek en een paar verbeterpunten zag.")
        + " Ik heb een voorbeeld gemaakt van hoe het eruit zou kunnen zien. "
        "Mag ik dat even doorsturen, of passeer ik eens langs?"
    )
    return {"subject": subject, "body": body, "call": call}
