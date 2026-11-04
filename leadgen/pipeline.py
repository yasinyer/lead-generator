"""Zoeken → samenvoegen → aanvullen → sites checken → scoren → opslaan."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import requests

from . import config, db, merge
from .checks import pagespeed
from .checks.browser import MobileChecker
from .checks.website import check_site, classify_url
from .scoring import classify_site, score_lead
from .sources import osm, places


class Stopped(Exception):
    """De gebruiker drukte op Stoppen."""


def _never() -> bool:
    return False


def google_plan(sectors, cities, budget: int) -> tuple[list[tuple[str, str]], int]:
    """Welke (gemeente, sector)-combinaties Google krijgt, en hoeveel pagina's per stuk.

    Grootste gemeenten eerst (volgorde van CITIES) en per gemeente alle sectoren, zodat een
    klein budget niet helemaal opgaat aan de eerste sector.
    """
    order = [c for c in config.CITIES if c in set(cities)]
    pairs = [(city, sector) for city in order for sector in sectors]
    if not pairs or budget <= 0:
        return [], 0
    if len(pairs) > budget:
        return pairs[:budget], 1
    return pairs, max(1, min(3, budget // len(pairs)))


def gather(sectors, cities, *, province, use_osm, use_places, radius, client, log,
           should_stop=_never, raw: list[dict] | None = None) -> list[dict]:
    raw = [] if raw is None else raw
    if use_osm:
        osm_down = False
        for sector in sectors:
            if osm_down:
                break
            label = config.SECTORS[sector]["label"].lower()
            log(f"OpenStreetMap doorzoeken naar {label}...")
            found = osm.search(sector, province=True, log=log) if province else None
            if province and found is not None:
                log(f"OSM: {len(found)} {label} in heel Limburg")
                raw += found
                continue
            if province:
                log("  Heel Limburg in één keer lukt niet: ik zoek per gemeente.")
            n = 0
            for city in (list(config.CITIES) if province else cities):
                if should_stop():
                    raise Stopped
                part = osm.search(sector, city=city, radius=radius, log=log)
                if part is None:
                    osm_down = True
                    log("! OpenStreetMap is nu niet bereikbaar: ik ga verder met Google alleen.")
                    break
                n += len(part)
                raw += part
                if not province:
                    log(f"OSM: {len(part)} {label} rond {city}")
            if province:
                log(f"OSM: {n} {label} in heel Limburg")

    if use_places:
        plan_cities = list(config.CITIES) if province else cities
        pairs, pages = google_plan(sectors, plan_cities, client.budget.max_calls)
        wanted = len(sectors) * len(plan_cities)
        if len(pairs) < wanted:
            log(f"! Google-budget ({client.budget.max_calls}) reikt voor {len(pairs)} van de {wanted} "
                "combinaties van sector en gemeente. De grootste gemeenten gaan voor. "
                "Kies minder gemeenten of verhoog Max. Google-calls.")
        for city, sector in pairs:
            if should_stop():
                raise Stopped
            if client.budget.used >= client.budget.max_calls:
                log(f"! Google-budget ({client.budget.max_calls} calls) op, rest overgeslagen")
                break
            found = places.search(client, sector, city, radius=radius, max_pages=pages)
            log(f"Google: {len(found)} {config.SECTORS[sector]['label'].lower()} in {city}")
            raw += found
    return raw


def enrich_with_places(leads: list[dict], client, log, should_stop=_never) -> list[dict]:
    """OSM-zaken zonder Google-match opzoeken voor reviews en rating."""
    todo = [l for l in leads if not l.get("place_id")]
    if not todo:
        return leads
    log(f"Aanvullen via Google: {len(todo)} zaken die alleen in OSM stonden")
    done = 0
    by_id = {id(l): i for i, l in enumerate(leads)}
    for lead in todo:
        if should_stop():
            break
        if client.budget.used >= client.budget.max_calls:
            log(f"! Places-budget op na {done} aanvullingen")
            break
        p = places.lookup(client, lead["name"], lead.get("city"), lead.get("lat"), lead.get("lon"))
        if not p:
            continue
        cand = places.parse_place(p, sector=lead["sector"], fallback_city=lead.get("city"))
        close = True
        if lead.get("lat") and cand.get("lat"):
            close = merge.haversine_m((lead["lat"], lead["lon"]), (cand["lat"], cand["lon"])) < 400
        if close and merge.name_similarity(lead["name"], cand["name"]) >= 0.6:
            leads[by_id[id(lead)]] = merge.combine(cand, lead)
            done += 1
    log(f"  {done} zaken aangevuld met Google-reviews")
    # nogmaals samenvoegen: een aangevulde zaak kan al als Google-resultaat in de lijst staan
    return merge.merge(leads)


def assess_websites(leads: list[dict], *, use_browser: bool, use_pagespeed: bool, log,
                    should_stop=_never) -> None:
    session = requests.Session()
    for lead in leads:
        lead["issues"] = []
        url = lead.get("website")
        cls = classify_url(url)
        if cls == "social" and "facebook" in (url or "") and not lead.get("facebook"):
            lead["facebook"] = url
        if cls == "none" and not lead.get("place_id"):
            cls = "unverified"  # alleen OSM weet van deze zaak; Google bevestigt niets
        lead["web_status"] = cls

    to_fetch = [l for l in leads if l["web_status"] in ("site", "builder")]
    log(f"Websites checken: {len(to_fetch)} sites, "
        f"{len(leads) - len(to_fetch)} zonder eigen site")

    def fetch(lead):
        return lead, check_site(lead["website"], session=session)

    with ThreadPoolExecutor(max_workers=8) as ex:
        http_results = dict((id(l), r) for l, r in ex.map(fetch, to_fetch))

    reachable = [l for l in to_fetch if http_results[id(l)]["reachable"]
                 and not http_results[id(l)].get("redirects_to")]

    psi_ex = ThreadPoolExecutor(max_workers=4)
    psi_futures = {}
    if use_pagespeed:
        if not config.PAGESPEED_API_KEY:
            log("! Geen API-key voor PageSpeed: snelheidscheck overgeslagen")
        else:
            for l in reachable:
                url = http_results[id(l)]["final_url"] or l["website"]
                psi_futures[id(l)] = psi_ex.submit(pagespeed.mobile_score, url, config.PAGESPEED_API_KEY)

    browser_results = {}
    if use_browser and reachable:
        with MobileChecker(config.SCREENSHOT_DIR, log=log) as mc:
            if mc.available:
                for i, l in enumerate(reachable, 1):
                    if should_stop():
                        log("  Gestopt: overige gsm-checks overgeslagen")
                        break
                    url = http_results[id(l)]["final_url"] or l["website"]
                    log(f"  gsm-check {i}/{len(reachable)}: {l['name']}")
                    browser_results[id(l)] = mc.check(url, l["name"])

    for l in to_fetch:
        res = http_results[id(l)]
        issues = list(res["issues"])
        b = browser_results.get(id(l)) or {}
        issues += b.get("issues", [])
        if b.get("screenshot"):
            l["screenshot"] = b["screenshot"]
        if res.get("emails") and not l.get("email"):
            l["email"] = res["emails"][0]
        if not l.get("facebook"):
            fb = [s for s in res.get("socials", []) if "facebook.com" in s]
            l["facebook"] = fb[0] if fb else None

        fut = psi_futures.get(id(l))
        if fut and should_stop() and not fut.done():
            fut.cancel()
            fut = None
        if fut:
            psi = fut.result()
            if psi and psi["score"] is not None:
                l["pagespeed"] = psi["score"]
                lcp = f" (grootste element na {psi['lcp']})" if psi.get("lcp") else ""
                if psi["score"] < 50:
                    issues.append({"code": "slow", "text": f"Traag op gsm: PageSpeed {psi['score']}/100{lcp}"})
                elif psi["score"] < 70:
                    issues.append({"code": "meh_speed", "text": f"Matig snel op gsm: PageSpeed {psi['score']}/100"})

        codes = {i["code"] for i in issues}
        if codes & {"offline", "broken"}:
            status = "offline"
        elif "placeholder" in codes:
            status = "placeholder"
        elif res.get("redirects_to"):
            status = res["redirects_to"]
        elif res.get("blocked") and not b.get("ok"):
            status = "unknown"
        elif l["web_status"] == "builder":
            issues.insert(0, {"code": "builder", "text": "Gratis sitebouwer-adres: oogt niet professioneel"})
            status = "builder"
        else:
            status = classify_site(issues)
        l["web_status"] = status
        l["issues"] = issues
        l["checked_at"] = db.now()
    psi_ex.shutdown(wait=not should_stop(), cancel_futures=should_stop())


def scan(sectors: list[str], cities: list[str], *, province: bool = False, use_osm: bool = True,
         use_places: bool = True, enrich: bool = True, use_browser: bool = True,
         use_pagespeed: bool = True, radius: int = config.DEFAULT_RADIUS_M,
         max_places_calls: int = config.PLACES_MAX_CALLS, conn=None, log=print,
         should_stop=_never) -> dict:
    unknown = [s for s in sectors if s not in config.SECTORS] + [c for c in cities if c not in config.CITIES]
    if unknown:
        raise ValueError(f"Onbekende sector/stad: {', '.join(unknown)}")
    if not province and not cities:
        raise ValueError("Kies minstens één stad, of heel Limburg")
    conn = conn or db.connect()

    client = None
    if use_places:
        if not config.GOOGLE_API_KEY:
            log("! Geen GOOGLE_API_KEY in .env: ik zoek alleen via OpenStreetMap (geen reviews)")
            use_places = False
        else:
            client = places.PlacesClient(config.GOOGLE_API_KEY, places.Budget(max_places_calls), log=log)

    raw: list[dict] = []
    stopped = False
    try:
        gather(sectors, cities, province=province, use_osm=use_osm, use_places=use_places,
               radius=radius, client=client, log=log, should_stop=should_stop, raw=raw)
    except Stopped:
        stopped = True
        log("Gestopt tijdens het zoeken: ik bewaar wat er al gevonden is.")
    leads = merge.merge(raw)
    log(f"{len(raw)} resultaten → {len(leads)} unieke zaken")
    if use_places and enrich and not stopped:
        leads = enrich_with_places(leads, client, log, should_stop=should_stop)
    leads = [l for l in leads if l.get("business_status") != "CLOSED_PERMANENTLY"]

    # Nieuwe zaken meteen bewaren, zodat ze er zijn ook als de site-checks onderbroken worden.
    for l in leads:
        if db.exists(conn, l["key"]):
            continue
        cls = classify_url(l.get("website"))
        if cls == "none" and not l.get("place_id"):
            cls = "unverified"
        prelim = {**l, "web_status": None if cls in ("site", "builder") else cls, "issues": []}
        prelim["score"] = score_lead(prelim)
        db.upsert_lead(conn, prelim)
    log(f"{len(leads)} zaken bewaard. Nu worden hun websites gecheckt...")

    assess_websites(leads, use_browser=use_browser, use_pagespeed=use_pagespeed, log=log,
                    should_stop=should_stop)

    for l in leads:
        l["score"] = score_lead(l)
        db.upsert_lead(conn, l)
    if should_stop():
        log("Scan gestopt. Wat al gecheckt was, is bewaard.")

    hot = sum(1 for l in leads if l["score"] >= 70)
    summary = {
        "total": len(leads),
        "hot": hot,
        "no_site": sum(1 for l in leads if l["web_status"] in ("none", "social", "directory")),
        "weak": sum(1 for l in leads if l["web_status"] in ("weak", "offline", "placeholder", "builder")),
        "places_calls": client.budget.used if client else 0,
    }
    summary["unverified"] = sum(1 for l in leads if l["web_status"] == "unverified")
    log(f"Klaar: {summary['total']} leads, {hot} toppers (score ≥ 70), "
        f"{summary['no_site']} zonder eigen site, {summary['weak']} met zwakke site. "
        f"Places-calls gebruikt: {summary['places_calls']}")
    if summary["unverified"]:
        log(f"Let op: van {summary['unverified']} zaken staat in OpenStreetMap geen website, "
            "maar dat is niet zeker. Met een Google API-key (Instellingen) weet je het wel zeker.")
    return summary
