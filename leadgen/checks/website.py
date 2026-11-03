"""Snelle HTTP-analyse van een website: bereikbaarheid, HTTPS, viewport, ouderdom, e-mail."""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .. import config
from ..merge import domain

SOCIAL = ("facebook.com", "fb.com", "fb.me", "instagram.com", "linktr.ee", "tiktok.com",
          "linkedin.com", "twitter.com", "x.com", "wa.me", "m.facebook.com")
DIRECTORY = ("goudengids.be", "pagesdor.be", "infobel.com", "tripadvisor.", "yelp.",
             "thefork.", "resto.be", "openingsuren.vlaanderen", "cylex", "kapsalons.be",
             "treatwell.", "salonized.com", "booksy.com", "google.com", "goo.gl",
             "maps.app.goo.gl", "takeaway.com", "ubereats.com", "deliveroo.")
FREE_BUILDERS = ("wixsite.com", "jimdosite.com", "jimdofree.com", "webnode.", "weebly.com",
                 "blogspot.com", "wordpress.com", "business.site", "sites.google.com",
                 "site123.me", "mystrikingly.com", "godaddysites.com")
PLACEHOLDER_PHRASES = (
    "domain is for sale", "domein is te koop", "this domain", "under construction",
    "coming soon", "binnenkort online", "website in opbouw", "site en construction",
    "parked", "geparkeerd", "deze website is nog niet", "nog geen website",
    "default web site page", "welcome to nginx", "it works!",
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_JUNK = ("example.", "sentry", "wixpress", "domain.com", "email.com", "yourname",
              "naam@", "jouw@", "uwnaam", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".webp",
              ".svg", "godaddy", "noreply", "no-reply")
COPYRIGHT_RE = re.compile(
    r"(?:©|&copy;|\(c\)|copyright)\s*(?:[^0-9<]{0,30}?)((?:19|20)\d{2})(?:\s*[-–]\s*((?:19|20)\d{2}))?",
    re.I,
)


def _matches(host: str, patterns) -> bool:
    """Domein-match: 'facebook.com' matcht ook 'm.facebook.com' maar niet 'notfacebook.com'.
    Een patroon dat op '.' eindigt (bv. 'tripadvisor.') matcht elke extensie."""
    for p in patterns:
        if p.endswith("."):
            if host.startswith(p) or ("." + p) in host:
                return True
        elif host == p or host.endswith("." + p):
            return True
    return False


def classify_url(url: str | None) -> str:
    """none | social | directory | builder | site"""
    if not url or not url.strip():
        return "none"
    host = domain(url) or ""
    if _matches(host, SOCIAL):
        return "social"
    if _matches(host, FREE_BUILDERS):
        return "builder"
    if _matches(host, DIRECTORY):
        return "directory"
    return "site"


def decode_cfemail(hexstr: str) -> str:
    key = int(hexstr[:2], 16)
    return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))


def extract_emails(html: str, soup: BeautifulSoup | None = None) -> list[str]:
    soup = soup or BeautifulSoup(html, "html.parser")
    found: list[str] = []
    for a in soup.select('a[href^="mailto:"]'):
        found.append(a["href"][7:].split("?")[0])
    for el in soup.select("[data-cfemail]"):
        try:
            found.append(decode_cfemail(el["data-cfemail"]))
        except (ValueError, KeyError):
            pass
    for a in soup.select('a[href*="/cdn-cgi/l/email-protection#"]'):
        try:
            found.append(decode_cfemail(a["href"].split("#", 1)[1]))
        except (ValueError, IndexError):
            pass
    text = soup.get_text(" ")
    text = re.sub(r"\s*(\[at\]|\(at\)| at )\s*", "@", text, flags=re.I)
    text = re.sub(r"\s*(\[dot\]|\(dot\))\s*", ".", text, flags=re.I)
    found += EMAIL_RE.findall(text)
    clean: list[str] = []
    for e in found:
        e = e.strip().strip(".").lower()
        if EMAIL_RE.fullmatch(e) and not any(j in e for j in EMAIL_JUNK) and e not in clean:
            clean.append(e)
    return clean


def analyse_html(html: str, final_url: str, *, today: date | None = None) -> dict:
    """Puur, testbaar: geeft issues + gevonden e-mails/social-links terug."""
    today = today or date.today()
    soup = BeautifulSoup(html, "html.parser")
    issues: list[dict] = []

    def add(code: str, text: str):
        issues.append({"code": code, "text": text})

    if urlparse(final_url).scheme != "https":
        add("no_https", "Geen HTTPS (browser toont 'Niet veilig')")

    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    if not viewport or "width" not in (viewport.get("content") or "").lower():
        add("no_viewport", "Geen mobiele viewport: site schaalt niet op gsm")

    years = []
    for m in COPYRIGHT_RE.finditer(html):
        years += [int(y) for y in m.groups() if y]
    years = [y for y in years if 1995 <= y <= today.year + 1]
    if years and max(years) <= today.year - 3:
        add("old_copyright", f"Copyright {max(years)}: site lijkt niet onderhouden")

    lower = html.lower()
    if ".swf" in lower or "shockwave-flash" in lower:
        add("flash", "Gebruikt Flash (werkt nergens meer)")
    if soup.find(["frameset", "frame"]):
        add("frames", "Gebruikt frames (verouderde techniek)")
    old_tags = len(soup.find_all(["font", "center", "marquee", "blink"]))
    layout_tables = len([t for t in soup.find_all("table") if t.find("table") or t.get("width")])
    if old_tags >= 3 or layout_tables >= 2:
        add("old_html", "Verouderde HTML (font-tags/tabel-layout)")

    gen = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
    generator = (gen.get("content") or "").strip() if gen else ""
    if re.search(r"frontpage|dreamweaver|joomla!? 1\.|wordpress [2-4]\.", generator, re.I):
        add("old_cms", f"Oud systeem: {generator}")

    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    if not title:
        add("no_title", "Geen paginatitel (slecht voor Google)")
    if not soup.find("meta", attrs={"name": re.compile("^description$", re.I)}):
        add("no_description", "Geen meta-omschrijving (slecht voor Google)")

    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    visible = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    if any(p in visible.lower() for p in PLACEHOLDER_PHRASES) and len(visible) < 1500:
        add("placeholder", "Placeholder/geparkeerde pagina, geen echte site")
    elif len(visible) < 200:
        add("thin", "Bijna geen inhoud op de homepage")

    socials = sorted({a["href"] for a in BeautifulSoup(html, "html.parser").select("a[href]")
                      if _matches(domain(a["href"]) or "", ("facebook.com", "instagram.com"))})
    return {
        "issues": issues,
        "emails": extract_emails(html),
        "socials": socials,
        "generator": generator,
        "title": title,
    }


def _contact_links(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    base_host = domain(base)
    for a in soup.select("a[href]"):
        href = a["href"]
        label = (a.get_text() + " " + href).lower()
        if any(w in label for w in ("contact", "over-ons", "over ons", "about", "impressum")):
            url = urljoin(base, href)
            if domain(url) == base_host and url not in links:
                links.append(url)
    return links[:2]


def check_site(url: str, *, session: requests.Session | None = None) -> dict:
    """Haal een site op en analyseer ze. Netwerkfouten worden issues, geen excepties."""
    session = session or requests.Session()
    headers = {"User-Agent": config.USER_AGENT, "Accept-Language": "nl-BE,nl;q=0.9"}
    if "://" not in url:
        url = "http://" + url
    result = {"url": url, "final_url": None, "status_code": None, "reachable": False,
              "blocked": False, "issues": [], "emails": [], "socials": []}
    try:
        r = session.get(url, headers=headers, timeout=15, allow_redirects=True)
    except requests.exceptions.SSLError:
        result["issues"].append({"code": "ssl_error", "text": "SSL-certificaat ongeldig of verlopen"})
        try:
            r = session.get(url.replace("https://", "http://"), headers=headers, timeout=15)
        except requests.RequestException:
            return result
    except requests.RequestException as e:
        kind = "Domein bestaat niet" if "Name or service" in str(e) or "getaddrinfo" in str(e) \
            else "Site reageert niet"
        result["issues"].append({"code": "offline", "text": f"{kind} (offline)"})
        return result

    if r.status_code in (404, 410) and urlparse(url).path.strip("/"):
        # Verouderde link naar een subpagina: kijk of de homepage wel werkt.
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
        try:
            rr = session.get(root, headers=headers, timeout=15, allow_redirects=True)
            if rr.ok:
                r = rr
        except requests.RequestException:
            pass

    result["status_code"] = r.status_code
    result["final_url"] = r.url
    if r.status_code in (401, 403, 429, 503):
        result["blocked"] = True  # bot-blokkade: browsercheck beslist
        result["reachable"] = True
        return result
    if r.status_code >= 400:
        result["issues"].append({"code": "broken", "text": f"Site geeft foutcode {r.status_code}"})
        return result

    result["reachable"] = True
    final_class = classify_url(r.url)
    if final_class in ("social", "directory"):
        result["redirects_to"] = final_class
        return result

    r.encoding = r.encoding or r.apparent_encoding
    analysis = analyse_html(r.text, r.url)
    result["issues"] += analysis["issues"]
    result["emails"] = analysis["emails"]
    result["socials"] = analysis["socials"]
    result["generator"] = analysis["generator"]

    if not result["emails"]:
        for link in _contact_links(r.text, r.url):
            try:
                cr = session.get(link, headers=headers, timeout=10)
                if cr.ok:
                    result["emails"] = extract_emails(cr.text)
                    if result["emails"]:
                        break
            except requests.RequestException:
                continue
    return result
