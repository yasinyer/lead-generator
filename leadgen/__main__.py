"""Gebruik:

  python -m leadgen scan --sector kapper --city Hasselt --city Genk
  python -m leadgen scan --sector restaurant --limburg
  python -m leadgen serve
  python -m leadgen export leads.csv
"""
from __future__ import annotations

import argparse
import sys

from . import config, db, pipeline


def main(argv=None):
    p = argparse.ArgumentParser(prog="leadgen", description="Vind lokale zaken met een zwakke of geen website.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Zoek en analyseer zaken")
    s.add_argument("--sector", "-s", action="append", default=[],
                   help=f"Sector (herhaalbaar of 'all'): {', '.join(config.SECTORS)}")
    s.add_argument("--city", "-c", action="append", default=[],
                   help="Gemeente (herhaalbaar), bv. Hasselt. Zie 'leadgen list'")
    s.add_argument("--limburg", action="store_true", help="Heel de provincie Limburg")
    s.add_argument("--radius", type=int, default=config.DEFAULT_RADIUS_M, help="Zoekstraal in meter")
    s.add_argument("--max-places-calls", type=int, default=config.PLACES_MAX_CALLS)
    s.add_argument("--no-osm", action="store_true")
    s.add_argument("--no-places", action="store_true")
    s.add_argument("--no-enrich", action="store_true", help="OSM-zaken niet aanvullen via Google")
    s.add_argument("--no-browser", action="store_true", help="Geen gsm-check/screenshots")
    s.add_argument("--no-pagespeed", action="store_true")

    v = sub.add_parser("serve", help="Start het dashboard")
    v.add_argument("--port", type=int, default=8765)
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--no-open", action="store_true", help="Browser niet automatisch openen")

    e = sub.add_parser("export", help="Exporteer leads naar CSV")
    e.add_argument("path")
    e.add_argument("--min-score", type=int, default=0)

    sub.add_parser("list", help="Toon beschikbare sectoren en gemeenten")

    a = p.parse_args(argv)

    if a.cmd == "list":
        print("Sectoren:")
        for k, v in config.SECTORS.items():
            print(f"  {k:<12} {v['label']}")
        print("\nGemeenten:\n  " + ", ".join(config.CITIES))
        return 0

    if a.cmd == "scan":
        sectors = list(config.SECTORS) if "all" in a.sector else a.sector
        if not sectors:
            p.error("geef minstens één --sector (of --sector all)")
        city_lookup = {c.lower(): c for c in config.CITIES}
        cities = []
        for c in a.city:
            if c.lower() not in city_lookup:
                p.error(f"onbekende gemeente '{c}'. Voeg ze toe aan CITIES in leadgen/config.py")
            cities.append(city_lookup[c.lower()])
        if not cities and not a.limburg:
            p.error("geef minstens één --city of gebruik --limburg")
        pipeline.scan(
            sectors, cities, province=a.limburg, use_osm=not a.no_osm, use_places=not a.no_places,
            enrich=not a.no_enrich, use_browser=not a.no_browser, use_pagespeed=not a.no_pagespeed,
            radius=a.radius, max_places_calls=a.max_places_calls,
        )
        print("\nBekijk de resultaten met: python -m leadgen serve")
        return 0

    if a.cmd == "serve":
        from .server import run

        run(a.host, a.port, open_browser=not a.no_open)
        return 0

    if a.cmd == "export":
        from .web.app import create_app

        client = create_app().test_client()
        r = client.get(f"/api/export.csv?min_score={a.min_score}")
        with open(a.path, "wb") as f:
            f.write(r.data)
        n = len(db.list_leads(db.connect(), min_score=a.min_score))
        print(f"{n} leads geëxporteerd naar {a.path}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
