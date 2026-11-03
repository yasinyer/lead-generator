from datetime import date

import pytest

from leadgen import db, merge, pipeline, scoring
from leadgen.checks import website
from leadgen.pitch import make_pitch
from leadgen.sources import osm, places


# ---------- URL-classificatie ----------
@pytest.mark.parametrize("url,expected", [
    (None, "none"),
    ("", "none"),
    ("https://www.facebook.com/kapsalonlisa", "social"),
    ("https://m.facebook.com/kapsalonlisa", "social"),
    ("instagram.com/lisa", "social"),
    ("https://www.goudengids.be/bedrijf/hasselt/123", "directory"),
    ("https://www.tripadvisor.be/Restaurant_Review", "directory"),
    ("https://lisa.wixsite.com/kapsalon", "builder"),
    ("https://sites.google.com/view/lisa", "builder"),
    ("https://kapsalon-lisa.business.site", "builder"),
    ("https://www.kapsalonlisa.be", "site"),
    ("https://fix.com", "site"),  # geen 'x.com'-match
    ("https://notfacebook.com", "site"),
])
def test_classify_url(url, expected):
    assert website.classify_url(url) == expected


# ---------- HTML-analyse ----------
OLD_SITE = """<html><head><title>Garage Jos</title><meta name="generator" content="Microsoft FrontPage 4.0"></head>
<body bgcolor="#ffffff"><center><font face="Arial">Welkom bij Garage Jos</font></center>
<table width="800"><tr><td><table><tr><td><font>Onderhoud en herstellingen van alle merken.
Wij staan al 30 jaar voor u klaar in Hasselt en omstreken. Bel ons voor een afspraak.</font></td></tr></table></td></tr></table>
<p>Mail: <a href="mailto:info@garagejos.be">info@garagejos.be</a></p>
<p>&copy; 2014 Garage Jos</p></body></html>"""

MODERN_SITE = """<html><head><title>Kapsalon Lisa</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Kapsalon in Hasselt"></head>
<body><main><h1>Kapsalon Lisa</h1><p>""" + ("Knippen, kleuren en stylen. " * 20) + """</p>
<a href="https://www.facebook.com/kapsalonlisa">Facebook</a>
<span class="__cf_email__" data-cfemail="543d3a323b14383d27357a3631">[email protected]</span>
<footer>© 2019 - 2026 Kapsalon Lisa</footer></main></body></html>"""


def codes(analysis):
    return {i["code"] for i in analysis["issues"]}


def test_analyse_old_site():
    a = website.analyse_html(OLD_SITE, "http://garagejos.be/", today=date(2026, 11, 3))
    c = codes(a)
    assert {"no_https", "no_viewport", "old_copyright", "old_html", "old_cms", "no_description"} <= c
    assert a["emails"] == ["info@garagejos.be"]


def test_analyse_modern_site():
    a = website.analyse_html(MODERN_SITE, "https://kapsalonlisa.be/", today=date(2026, 11, 3))
    assert codes(a) == set()
    assert a["socials"] == ["https://www.facebook.com/kapsalonlisa"]
    assert "info@lisa.be" in a["emails"]  # Cloudflare-beveiligd adres gedecodeerd


def test_placeholder_detection():
    html = '<html><head><title>x</title><meta name="viewport" content="width=device-width"></head><body>Website in opbouw, binnenkort online!</body></html>'
    assert "placeholder" in codes(website.analyse_html(html, "https://x.be"))


def test_email_obfuscation_and_junk():
    html = "<p>contact: jan [at] bakkerij-jan.be</p><img src='logo@2x.png'><p>naam@voorbeeld.com</p><p>Info@Frituur.be.</p>"
    assert website.extract_emails(html) == ["jan@bakkerij-jan.be", "info@frituur.be"]


def test_cfemail_roundtrip():
    key = 0x54
    enc = f"{key:02x}" + "".join(f"{ord(ch) ^ key:02x}" for ch in "info@lisa.be")
    assert website.decode_cfemail(enc) == "info@lisa.be"


# ---------- samenvoegen ----------
def test_normalize_phone():
    assert merge.normalize_phone("011 22 33 44") == "3211223344"
    assert merge.normalize_phone("+32 11 22 33 44") == "3211223344"
    assert merge.normalize_phone("0032 11/22.33.44") == "3211223344"


def test_merge_osm_and_places():
    g = {"source": "places", "place_id": "abc", "name": "Kapsalon Lisa BV", "phone": "011 22 33 44",
         "lat": 50.93, "lon": 5.338, "rating": 4.8, "review_count": 120, "city": "Hasselt", "sector": "kapper"}
    o = {"source": "osm", "osm_id": "node/1", "name": "Kapsalon Lisa", "phone": None,
         "email": "lisa@x.be", "lat": 50.9301, "lon": 5.3381, "city": "Hasselt", "sector": "kapper"}
    other = {"source": "osm", "osm_id": "node/2", "name": "Frituur De Kroon", "lat": 50.94, "lon": 5.35,
             "city": "Hasselt", "sector": "frituur"}
    out = merge.merge([o, g, other])
    assert len(out) == 2
    lisa = next(l for l in out if l.get("place_id") == "abc")
    assert lisa["email"] == "lisa@x.be" and lisa["rating"] == 4.8
    assert lisa["sources"] == {"osm", "places"}
    assert lisa["key"] == "g:abc"


def test_merge_by_phone_even_if_names_differ():
    a = {"source": "places", "place_id": "p1", "name": "Garage Peeters", "phone": "011 11 11 11"}
    b = {"source": "osm", "osm_id": "way/9", "name": "Peeters Autos", "phone": "+3211111111"}
    assert len(merge.merge([a, b])) == 1


# ---------- bronnen parsen ----------
def test_osm_parse_and_query():
    el = {"type": "way", "id": 42, "center": {"lat": 50.9, "lon": 5.3}, "tags": {
        "name": "Kiné Centrum", "addr:street": "Kerkstraat", "addr:housenumber": "5",
        "addr:postcode": "3500", "addr:city": "Hasselt", "contact:phone": "011 12 34 56",
        "contact:website": "https://facebook.com/kine"}}
    lead = osm.parse_element(el, sector="kinesist", fallback_city="Hasselt")
    assert lead["address"] == "Kerkstraat 5, 3500 Hasselt"
    assert lead["facebook"] == "https://facebook.com/kine"
    assert lead["lat"] == 50.9 and lead["osm_id"] == "way/42"
    q = osm.build_query(["shop=hairdresser"], around=(50.93, 5.33, 3000))
    assert 'nwr["shop"="hairdresser"]["name"](around:3000,50.93,5.33);' in q
    assert 'BE-VLI' in osm.build_query(["shop=bakery"], province=True)


def test_places_parse():
    p = {"id": "xyz", "displayName": {"text": "Bakkerij Jan"}, "formattedAddress": "Markt 1, 3500 Hasselt",
         "addressComponents": [{"longText": "Hasselt", "types": ["locality", "political"]}],
         "rating": 4.6, "userRatingCount": 88, "location": {"latitude": 50.93, "longitude": 5.33},
         "businessStatus": "OPERATIONAL"}
    lead = places.parse_place(p, sector="bakker", fallback_city="Genk")
    assert lead["name"] == "Bakkerij Jan" and lead["city"] == "Hasselt"
    assert lead["website"] is None and lead["review_count"] == 88


def test_places_budget():
    b = places.Budget(2)
    assert b.take() and b.take() and not b.take()


# ---------- scoring ----------
def test_scoring_order():
    no_site_good_reviews = {"web_status": "none", "issues": [], "rating": 4.7, "review_count": 160, "phone": "x"}
    weak_site = {"web_status": "weak", "issues": [{"code": "no_viewport"}, {"code": "no_https"}],
                 "rating": 4.3, "review_count": 40}
    fine_site = {"web_status": "ok", "issues": [{"code": "no_description"}], "rating": 4.8, "review_count": 300}
    bad_reviews = {"web_status": "none", "issues": [], "rating": 2.5, "review_count": 4}
    s = [scoring.score_lead(x) for x in (no_site_good_reviews, weak_site, fine_site, bad_reviews)]
    assert s[0] >= 90
    assert s[0] > s[1] > s[2]
    assert s[0] > s[3]
    assert scoring.classify_site([{"code": "no_description"}]) == "ok"
    assert scoring.classify_site([{"code": "overflow"}]) == "weak"


# ---------- pitch ----------
def test_pitch_mentions_reviews_and_issues():
    lead = {"name": "Garage Jos", "web_status": "weak", "rating": 4.6, "review_count": 87,
            "issues": [{"code": "overflow", "text": ""}, {"code": "no_https", "text": ""}]}
    p = make_pitch(lead)
    assert "4,6 sterren hebben uit 87 reviews" in p["body"]
    assert "zijwaarts scrollen" in p["body"] and "Niet veilig" in p["body"]
    assert "€" in p["body"]
    assert make_pitch({"name": "X", "web_status": "none", "issues": []})["subject"] == "Een website voor X?"


# ---------- database ----------
def test_db_upsert_keeps_user_fields(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    lead = {"key": "g:1", "name": "Zaak", "sector": "kapper", "city": "Hasselt", "score": 80,
            "issues": [{"code": "no_https", "text": "Geen HTTPS"}], "sources": {"places"}}
    lid = db.upsert_lead(conn, lead)
    db.update_user_fields(conn, lid, status="gecontacteerd", notes="terugbellen vrijdag")
    db.upsert_lead(conn, {**lead, "score": 85, "phone": "011"})
    row = db.get_lead(conn, lid)
    assert row["status"] == "gecontacteerd" and row["notes"] == "terugbellen vrijdag"
    assert row["score"] == 85 and row["phone"] == "011"
    assert row["issues"][0]["code"] == "no_https"
    assert [l["id"] for l in db.list_leads(conn, min_score=80, q="Zaak")] == [lid]


# ---------- pipeline (zonder netwerk) ----------
def test_scan_offline(monkeypatch, tmp_path):
    from leadgen import config

    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(config, "PAGESPEED_API_KEY", "")
    fake_osm = [
        {"source": "osm", "osm_id": "node/1", "name": "Kapper Zonder Site", "sector": "kapper",
         "city": "Hasselt", "phone": "011 00 00 01", "lat": 50.93, "lon": 5.33},
        {"source": "osm", "osm_id": "node/2", "name": "Kapper Facebook", "sector": "kapper",
         "city": "Hasselt", "website": "https://facebook.com/kf", "lat": 50.94, "lon": 5.34},
        {"source": "osm", "osm_id": "node/3", "name": "Kapper Oud", "sector": "kapper",
         "city": "Hasselt", "website": "http://kapperoud.be", "lat": 50.95, "lon": 5.35},
    ]
    monkeypatch.setattr(osm, "search", lambda *a, **k: fake_osm)
    monkeypatch.setattr(pipeline, "check_site", lambda url, session=None: {
        "url": url, "final_url": url, "reachable": True, "issues": [{"code": "no_viewport", "text": "x"}],
        "emails": ["info@kapperoud.be"], "socials": []})
    conn = db.connect(tmp_path / "s.db")
    summary = pipeline.scan(["kapper"], ["Hasselt"], use_browser=False, conn=conn, log=lambda m: None)
    assert summary["total"] == 3
    rows = {r["name"]: r for r in db.list_leads(conn)}
    assert rows["Kapper Zonder Site"]["web_status"] == "none"
    assert rows["Kapper Facebook"]["web_status"] == "social"
    assert rows["Kapper Facebook"]["facebook"] == "https://facebook.com/kf"
    assert rows["Kapper Oud"]["web_status"] == "weak"
    assert rows["Kapper Oud"]["email"] == "info@kapperoud.be"
