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
    # Alleen OSM zegt "geen website": niet zeker, dus geen topscore.
    assert rows["Kapper Zonder Site"]["web_status"] == "unverified"
    assert rows["Kapper Zonder Site"]["score"] < 50
    assert rows["Kapper Facebook"]["web_status"] == "social"
    assert rows["Kapper Facebook"]["facebook"] == "https://facebook.com/kf"
    assert rows["Kapper Oud"]["web_status"] == "weak"
    assert rows["Kapper Oud"]["email"] == "info@kapperoud.be"


# ---------- instellingen ----------
@pytest.fixture
def restore_config(monkeypatch):
    from leadgen import config

    for name, (attr, _) in config.SETTINGS.items():
        monkeypatch.setattr(config, attr, getattr(config, attr))
    monkeypatch.setattr(config, "PAGESPEED_API_KEY", config.PAGESPEED_API_KEY)
    monkeypatch.delenv("PAGESPEED_API_KEY", raising=False)
    return config


def test_save_settings_roundtrip(tmp_path, restore_config):
    config = restore_config
    env = tmp_path / ".env"
    env.write_text("# eigen commentaar\nGOOGLE_API_KEY=oud\nANDERS=blijft\n")
    config.save_settings({"GOOGLE_API_KEY": "AIzaNIEUW1234", "DESIGNER_NAME": 'Jan "J" Peeters',
                          "PLACES_MAX_CALLS": "200", "ONBEKEND": "x"}, env)
    from dotenv import dotenv_values

    vals = dotenv_values(env)
    assert vals["GOOGLE_API_KEY"] == "AIzaNIEUW1234"
    assert vals["DESIGNER_NAME"] == 'Jan "J" Peeters'
    assert vals["ANDERS"] == "blijft" and "ONBEKEND" not in vals
    assert env.read_text().startswith("# eigen commentaar")
    assert config.PLACES_MAX_CALLS == 200 and config.PAGESPEED_API_KEY == "AIzaNIEUW1234"
    assert config.current_settings()["GOOGLE_API_KEY"] == {"set": True, "hint": "••••1234"}


def test_settings_api_keeps_key_when_empty(tmp_path, restore_config, monkeypatch):
    from leadgen.web.app import create_app

    config = restore_config
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    client = create_app(tmp_path / "x.db").test_client()
    client.post("/api/settings", json={"GOOGLE_API_KEY": "AIzaGEHEIM5678", "DESIGNER_NAME": "Jan"})
    r = client.post("/api/settings", json={"GOOGLE_API_KEY": "", "DESIGNER_NAME": "Jan P"}).get_json()
    assert r["GOOGLE_API_KEY"]["set"] and "GEHEIM" not in str(r)
    assert config.GOOGLE_API_KEY == "AIzaGEHEIM5678" and config.DESIGNER_NAME == "Jan P"
    assert client.get("/api/meta").get_json()["designer_set"] is True
    r = client.post("/api/settings", json={"remove_key": True}).get_json()
    assert r["GOOGLE_API_KEY"]["set"] is False
    assert client.post("/api/settings", json={"PLACES_MAX_CALLS": "veel"}).status_code == 400


# ---------- beveiliging en app-levenscyclus ----------
def test_requests_guard_and_ping(tmp_path):
    from leadgen.web.app import create_app

    app = create_app(tmp_path / "g.db")
    c = app.test_client()
    # Een andere website kan geen 'simple request' (text/plain) sturen om iets te wijzigen.
    r = c.post("/api/settings", data='{"DESIGNER_NAME": "x"}', content_type="text/plain")
    assert r.status_code == 415
    # DNS-rebinding: een vreemde Host-header wordt geweigerd.
    assert c.get("/api/meta", headers={"Host": "evil.example:8765"}).status_code == 403
    assert c.get("/api/meta").get_json()["app"] == "leadgen"
    state = app.config["LEADGEN_STATE"]
    state["last_seen"] = 0
    assert c.post("/api/ping", json={}).status_code == 200
    assert state["last_seen"] > 0


def test_find_running_and_free_port():
    import socket

    from leadgen import server

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        busy = s.getsockname()[1]
        assert server.free_port("127.0.0.1", busy) != busy
    assert server.find_running("127.0.0.1", 1) is None



def test_google_confirms_no_website():
    leads = [{"name": "A", "place_id": "g1", "website": None, "sources": {"places"}},
             {"name": "B", "osm_id": "node/1", "website": None, "sources": {"osm"}}]
    pipeline.assess_websites(leads, use_browser=False, use_pagespeed=False, log=lambda m: None)
    assert [l["web_status"] for l in leads] == ["none", "unverified"]
    assert make_pitch(leads[1])["body"].count("vond er geen") == 1


class _Resp:
    def __init__(self, url, status, text=""):
        self.url, self.status_code, self.text, self.ok = url, status, text, status < 400
        self.encoding, self.apparent_encoding = "utf-8", "utf-8"


class _Session:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **kw):
        status, text = self.pages.get(url, (404, ""))
        return _Resp(url, status, text)


def test_broken_deep_link_falls_back_to_homepage():
    home = MODERN_SITE
    sess = _Session({"https://salon.be/": (200, home)})
    r = website.check_site("https://salon.be/nl/oude-pagina", session=sess)
    assert r["reachable"] and not any(i["code"] == "broken" for i in r["issues"])
    assert r["final_url"] == "https://salon.be/"
    r = website.check_site("https://kapot.be/", session=_Session({}))
    assert any(i["code"] == "broken" for i in r["issues"])


def test_window_mode_endpoints(tmp_path, monkeypatch):
    import webbrowser

    from leadgen.web import app as webapp

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(webapp.sys, "platform", "linux")
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))
    c = webapp.create_app(tmp_path / "w.db").test_client()
    # alleen gewone web-, mail- en tel-links, niets anders (geen file://, geen apps)
    assert c.post("/api/open", json={"url": "file:///etc/passwd"}).status_code == 400
    assert c.post("/api/open", json={"url": "https://maps.google.com/x"}).status_code == 200
    assert opened == ["https://maps.google.com/x"]
    r = c.post("/api/export-file?min_score=0", json={}).get_json()
    saved = tmp_path / "Downloads" / r["name"]
    assert saved.exists() and saved.read_text(encoding="utf-8").lstrip("﻿").startswith("Score;Naam")


def test_old_windowless_instance_is_found_and_stopped():
    """Een oudere versie zonder venster moet plaatsmaken voor het app-venster."""
    import http.server
    import json as _json
    import threading

    from leadgen import server

    class Old(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = _json.dumps({"app": "leadgen", "window": False}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            assert self.path == "/api/shutdown"
            assert self.headers["Content-Type"] == "application/json"
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            threading.Thread(target=httpd.shutdown).start()

    httpd = http.server.HTTPServer(("127.0.0.1", 0), Old)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    url, meta = server.running_instance("127.0.0.1", port)
    assert meta["window"] is False
    httpd_close = httpd.server_close
    assert server.stop_instance(url, timeout=5)
    t.join(2)
    httpd_close()
    assert server.running_instance("127.0.0.1", port) is None
