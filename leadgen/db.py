"""SQLite-opslag. Bij een nieuwe scan blijven jouw status en notities behouden."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT UNIQUE NOT NULL,
    place_id        TEXT,
    osm_id          TEXT,
    sources         TEXT,
    name            TEXT NOT NULL,
    sector          TEXT,
    city            TEXT,
    address         TEXT,
    phone           TEXT,
    email           TEXT,
    website         TEXT,
    facebook        TEXT,
    rating          REAL,
    review_count    INTEGER,
    maps_url        TEXT,
    lat             REAL,
    lon             REAL,
    business_status TEXT,
    web_status      TEXT,
    issues          TEXT,
    pagespeed       INTEGER,
    screenshot      TEXT,
    score           INTEGER,
    status          TEXT DEFAULT 'nieuw',
    notes           TEXT DEFAULT '',
    created_at      TEXT,
    updated_at      TEXT,
    checked_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
"""

# Velden die een scan mag overschrijven (status/notes horen bij de gebruiker).
SCAN_FIELDS = [
    "place_id", "osm_id", "sources", "name", "sector", "city", "address", "phone",
    "email", "website", "facebook", "rating", "review_count", "maps_url", "lat",
    "lon", "business_status", "web_status", "issues", "pagespeed", "screenshot",
    "score", "checked_at",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_lead(conn: sqlite3.Connection, lead: dict) -> int:
    data = {f: lead.get(f) for f in SCAN_FIELDS}
    if isinstance(data["issues"], (list, tuple)):
        data["issues"] = json.dumps(data["issues"], ensure_ascii=False)
    if isinstance(data["sources"], (list, tuple, set)):
        data["sources"] = ",".join(sorted(data["sources"]))
    ts = now()
    existing = conn.execute("SELECT id FROM leads WHERE key = ?", (lead["key"],)).fetchone()
    if existing:
        # Lege waarden overschrijven geen eerder gevonden gegevens.
        sets = ", ".join(f"{f} = COALESCE(:{f}, {f})" for f in SCAN_FIELDS)
        conn.execute(
            f"UPDATE leads SET {sets}, updated_at = :ts WHERE id = :id",
            {**data, "ts": ts, "id": existing["id"]},
        )
        conn.commit()
        return existing["id"]
    cols = ["key", *SCAN_FIELDS, "created_at", "updated_at"]
    cur = conn.execute(
        f"INSERT INTO leads ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})",
        {**data, "key": lead["key"], "created_at": ts, "updated_at": ts},
    )
    conn.commit()
    return cur.lastrowid


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["issues"] = json.loads(d.get("issues") or "[]")
    except (TypeError, json.JSONDecodeError):
        d["issues"] = []
    return d


def list_leads(
    conn: sqlite3.Connection,
    *,
    sector: str | None = None,
    city: str | None = None,
    status: str | None = None,
    web_status: str | None = None,
    min_score: int | None = None,
    min_reviews: int | None = None,
    q: str | None = None,
) -> list[dict]:
    where, params = [], []
    if sector:
        where.append("sector = ?")
        params.append(sector)
    if city:
        where.append("city = ?")
        params.append(city)
    if status:
        where.append("status = ?")
        params.append(status)
    if web_status:
        where.append("web_status = ?")
        params.append(web_status)
    if min_score is not None:
        where.append("score >= ?")
        params.append(min_score)
    if min_reviews is not None:
        where.append("COALESCE(review_count, 0) >= ?")
        params.append(min_reviews)
    if q:
        where.append("(name LIKE ? OR address LIKE ? OR notes LIKE ?)")
        params += [f"%{q}%"] * 3
    sql = "SELECT * FROM leads"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score DESC, review_count DESC, name"
    return [row_to_dict(r) for r in conn.execute(sql, params)]


def get_lead(conn: sqlite3.Connection, lead_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return row_to_dict(row) if row else None


def update_user_fields(conn: sqlite3.Connection, lead_id: int, *, status=None, notes=None) -> None:
    if status is not None:
        conn.execute("UPDATE leads SET status = ?, updated_at = ? WHERE id = ?", (status, now(), lead_id))
    if notes is not None:
        conn.execute("UPDATE leads SET notes = ?, updated_at = ? WHERE id = ?", (notes, now(), lead_id))
    conn.commit()


def distinct(conn: sqlite3.Connection, column: str) -> list[str]:
    assert column in {"sector", "city", "web_status", "status"}
    return [r[0] for r in conn.execute(
        f"SELECT DISTINCT {column} FROM leads WHERE {column} IS NOT NULL ORDER BY {column}"
    )]
