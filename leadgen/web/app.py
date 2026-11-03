"""Lokaal dashboard: leads bekijken, filteren, opvolgen, scans starten en exporteren."""
from __future__ import annotations

import csv
import io
import threading
import traceback
from importlib.util import find_spec

from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory

from .. import config, db, pipeline
from ..pitch import make_pitch
from ..scoring import WEB_STATUS_LABELS

CSV_COLUMNS = [
    ("score", "Score"), ("name", "Naam"), ("sector", "Sector"), ("city", "Gemeente"),
    ("address", "Adres"), ("phone", "Telefoon"), ("email", "E-mail"), ("website", "Website"),
    ("facebook", "Facebook"), ("web_status", "Website-status"), ("issues", "Problemen"),
    ("pagespeed", "PageSpeed"), ("rating", "Rating"), ("review_count", "Reviews"),
    ("maps_url", "Google Maps"), ("status", "Opvolging"), ("notes", "Notities"),
]


def create_app(db_path=None) -> Flask:
    app = Flask(__name__)
    conn = db.connect(db_path)
    lock = threading.Lock()
    job = {"running": False, "log": [], "summary": None, "error": None}

    def filters():
        a = request.args
        def num(k):
            v = a.get(k)
            return int(v) if v not in (None, "") else None
        return dict(sector=a.get("sector") or None, city=a.get("city") or None,
                    status=a.get("status") or None, web_status=a.get("web_status") or None,
                    min_score=num("min_score"), min_reviews=num("min_reviews"), q=a.get("q") or None)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/meta")
    def meta():
        return jsonify({
            "sectors": {k: v["label"] for k, v in config.SECTORS.items()},
            "cities": list(config.CITIES),
            "statuses": config.STATUSES,
            "web_statuses": WEB_STATUS_LABELS,
            "has_google_key": bool(config.GOOGLE_API_KEY),
            "has_pagespeed_key": bool(config.PAGESPEED_API_KEY),
            "has_playwright": find_spec("playwright") is not None,
            "default_radius": config.DEFAULT_RADIUS_M,
            "places_max_calls": config.PLACES_MAX_CALLS,
            "designer_set": bool(config.DESIGNER_NAME),
        })

    @app.get("/api/leads")
    def leads():
        with lock:
            rows = db.list_leads(conn, **filters())
        return jsonify(rows)

    @app.get("/api/stats")
    def stats():
        with lock:
            r = conn.execute("""
                SELECT COUNT(*) total,
                  SUM(score >= 70) hot,
                  SUM(web_status IN ('none','social','directory')) no_site,
                  SUM(web_status IN ('weak','offline','placeholder','builder')) weak,
                  SUM(status IN ('gecontacteerd','opvolgen')) contacted,
                  SUM(status = 'klant') clients
                FROM leads""").fetchone()
        return jsonify({k: (r[k] or 0) for k in r.keys()})

    @app.get("/api/leads/<int:lead_id>")
    def lead_detail(lead_id):
        with lock:
            lead = db.get_lead(conn, lead_id)
        if not lead:
            abort(404)
        lead["pitch"] = make_pitch(lead)
        return jsonify(lead)

    @app.patch("/api/leads/<int:lead_id>")
    def lead_update(lead_id):
        body = request.get_json(force=True) or {}
        status = body.get("status")
        if status is not None and status not in dict(config.STATUSES):
            abort(400)
        with lock:
            db.update_user_fields(conn, lead_id, status=status, notes=body.get("notes"))
            lead = db.get_lead(conn, lead_id)
        return jsonify(lead)

    @app.get("/api/export.csv")
    def export():
        with lock:
            rows = db.list_leads(conn, **filters())
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")  # ';' opent correct in Excel met Belgische instellingen
        w.writerow([h for _, h in CSV_COLUMNS])
        for r in rows:
            r = dict(r)
            r["issues"] = " | ".join(i["text"] for i in r["issues"])
            r["web_status"] = WEB_STATUS_LABELS.get(r["web_status"], r["web_status"])
            r["sector"] = config.SECTORS.get(r["sector"], {}).get("label", r["sector"])
            w.writerow(["" if r.get(k) is None else r[k] for k, _ in CSV_COLUMNS])
        return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=leads.csv"})

    @app.get("/screenshots/<path:fname>")
    def screenshot(fname):
        return send_from_directory(config.SCREENSHOT_DIR, fname)

    @app.post("/api/scan")
    def start_scan():
        if job["running"]:
            return jsonify({"error": "Er loopt al een scan"}), 409
        b = request.get_json(force=True) or {}
        sectors, cities = b.get("sectors") or [], b.get("cities") or []
        province = bool(b.get("province"))
        if not sectors or (not cities and not province):
            return jsonify({"error": "Kies minstens één sector en één gemeente (of heel Limburg)"}), 400
        job.update(running=True, log=[], summary=None, error=None)

        def log(msg):
            job["log"].append(str(msg))

        def run():
            try:
                scan_conn = db.connect(db_path)
                job["summary"] = pipeline.scan(
                    sectors, cities, province=province,
                    use_osm=b.get("osm", True), use_places=b.get("places", True),
                    enrich=b.get("enrich", True), use_browser=b.get("browser", True),
                    use_pagespeed=b.get("pagespeed", True),
                    radius=int(b.get("radius") or config.DEFAULT_RADIUS_M),
                    max_places_calls=int(b.get("max_places_calls") or config.PLACES_MAX_CALLS),
                    conn=scan_conn, log=log)
                scan_conn.close()
            except Exception as e:  # tonen in het dashboard i.p.v. stil falen
                job["error"] = str(e)
                log(traceback.format_exc())
            finally:
                job["running"] = False

        threading.Thread(target=run, daemon=True).start()
        return jsonify({"ok": True})

    @app.get("/api/scan/status")
    def scan_status():
        since = int(request.args.get("since", 0))
        return jsonify({"running": job["running"], "log": job["log"][since:], "next": len(job["log"]),
                        "summary": job["summary"], "error": job["error"]})

    return app
