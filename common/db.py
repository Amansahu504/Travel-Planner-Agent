"""SQLite operational database for MCP Server 2 (flights/hotels/activities/bookings).

Design notes
------------
* SQLite is used for relational queries and booking mutations; the seed data
  lives in versioned CSV files under data/seed/ (spec 9).
* `init_db()` creates the schema and, if the tables are empty, loads the CSV
  seed. It is safe to call repeatedly (idempotent).
* A cross-process file lock guards writes so concurrent MCP tool calls from the
  agents don't collide.
* ALL booking functionality is mock/demo only — no real money moves.
"""
from __future__ import annotations

import csv
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date

from filelock import FileLock

from common.config import (
    TRAVEL_DB, FLIGHTS_CSV, HOTELS_CSV, ACTIVITIES_CSV, BOOKINGS_CSV,
)

_LOCK = FileLock(str(TRAVEL_DB) + ".lock")

SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
    flight_id       TEXT PRIMARY KEY,
    airline         TEXT,
    origin          TEXT,
    destination     TEXT,
    departure_date  TEXT,
    return_date     TEXT,
    price           REAL,
    available_seats INTEGER,
    class           TEXT
);
CREATE TABLE IF NOT EXISTS hotels (
    hotel_id        TEXT PRIMARY KEY,
    hotel_name      TEXT,
    destination     TEXT,
    rating          REAL,
    price_per_night REAL,
    available_rooms INTEGER,
    category        TEXT
);
CREATE TABLE IF NOT EXISTS activities (
    activity_id     TEXT PRIMARY KEY,
    destination     TEXT,
    activity_name   TEXT,
    category        TEXT,
    price           REAL,
    duration        TEXT,
    rating          REAL
);
CREATE TABLE IF NOT EXISTS bookings (
    booking_id      TEXT PRIMARY KEY,
    booking_type    TEXT,
    item_id         TEXT,
    traveler_name   TEXT,
    booking_date    TEXT,
    status          TEXT,
    total_cost      REAL
);
"""

# CSV column order per table (also the public field order).
COLUMNS = {
    "flights": ["flight_id", "airline", "origin", "destination", "departure_date",
                "return_date", "price", "available_seats", "class"],
    "hotels": ["hotel_id", "hotel_name", "destination", "rating", "price_per_night",
               "available_rooms", "category"],
    "activities": ["activity_id", "destination", "activity_name", "category",
                   "price", "duration", "rating"],
    "bookings": ["booking_id", "booking_type", "item_id", "traveler_name",
                 "booking_date", "status", "total_cost"],
}

_NUMERIC = {"price", "price_per_night", "rating", "total_cost",
            "available_seats", "available_rooms"}


@contextmanager
def _connect():
    TRAVEL_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TRAVEL_DB))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _coerce(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k in _NUMERIC and v not in (None, ""):
            try:
                out[k] = float(v) if k in {"price", "price_per_night", "rating", "total_cost"} else int(float(v))
            except (TypeError, ValueError):
                out[k] = v
        else:
            out[k] = v
    return out


def _seed_table(conn: sqlite3.Connection, table: str, csv_path) -> int:
    if not csv_path.exists():
        return 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return 0
    cols = COLUMNS[table]
    placeholders = ", ".join("?" for _ in cols)
    conn.executemany(
        f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
        [[r.get(c, "") for c in cols] for r in rows],
    )
    return len(rows)


def init_db(force_reseed: bool = False) -> dict:
    """Create schema and load CSV seed if tables are empty. Idempotent."""
    with _LOCK:
        with _connect() as conn:
            conn.executescript(SCHEMA)
            counts = {}
            for table, csv_path in (
                ("flights", FLIGHTS_CSV), ("hotels", HOTELS_CSV),
                ("activities", ACTIVITIES_CSV), ("bookings", BOOKINGS_CSV),
            ):
                existing = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if force_reseed:
                    conn.execute(f"DELETE FROM {table}")
                    existing = 0
                if existing == 0:
                    counts[table] = _seed_table(conn, table, csv_path)
                else:
                    counts[table] = existing
    return counts


# ---- read helpers (used by search tools) ----
def _query(sql: str, params: tuple) -> list[dict]:
    with _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def search_flights(origin=None, destination=None, departure_date=None,
                   return_date=None, max_price=None, limit=20) -> list[dict]:
    where, params = [], []
    if origin:
        where.append("LOWER(origin) = LOWER(?)"); params.append(origin.strip())
    if destination:
        where.append("LOWER(destination) = LOWER(?)"); params.append(destination.strip())
    if departure_date:
        where.append("departure_date = ?"); params.append(departure_date.strip())
    if return_date:
        where.append("return_date = ?"); params.append(return_date.strip())
    if max_price is not None:
        where.append("price <= ?"); params.append(float(max_price))
    where.append("available_seats > 0")
    sql = "SELECT * FROM flights"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY price ASC LIMIT ?"; params.append(int(limit))
    return _query(sql, tuple(params))


def search_hotels(destination=None, max_price_per_night=None, minimum_rating=None,
                  category=None, limit=20) -> list[dict]:
    where, params = [], []
    if destination:
        where.append("LOWER(destination) = LOWER(?)"); params.append(destination.strip())
    if max_price_per_night is not None:
        where.append("price_per_night <= ?"); params.append(float(max_price_per_night))
    if minimum_rating is not None:
        where.append("rating >= ?"); params.append(float(minimum_rating))
    if category:
        where.append("LOWER(category) = LOWER(?)"); params.append(category.strip())
    where.append("available_rooms > 0")
    sql = "SELECT * FROM hotels"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY rating DESC, price_per_night ASC LIMIT ?"; params.append(int(limit))
    return _query(sql, tuple(params))


def search_activities(destination=None, category=None, max_price=None, limit=20) -> list[dict]:
    where, params = [], []
    if destination:
        where.append("LOWER(destination) = LOWER(?)"); params.append(destination.strip())
    if category:
        where.append("LOWER(category) = LOWER(?)"); params.append(category.strip())
    if max_price is not None:
        where.append("price <= ?"); params.append(float(max_price))
    sql = "SELECT * FROM activities"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY rating DESC LIMIT ?"; params.append(int(limit))
    return _query(sql, tuple(params))


# ---- booking mutations (mock/demo) ----
def create_booking(booking_type: str, item_id: str, traveler_name: str,
                   total_cost: float) -> dict:
    booking_id = "BK-" + uuid.uuid4().hex[:8].upper()
    row = {
        "booking_id": booking_id,
        "booking_type": booking_type,
        "item_id": item_id,
        "traveler_name": traveler_name,
        "booking_date": date.today().isoformat(),
        "status": "confirmed",
        "total_cost": float(total_cost),
    }
    with _LOCK:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO bookings VALUES (?,?,?,?,?,?,?)",
                [row[c] for c in COLUMNS["bookings"]],
            )
    return row


def get_booking(booking_id: str) -> dict | None:
    rows = _query("SELECT * FROM bookings WHERE booking_id = ?", (booking_id.strip(),))
    return rows[0] if rows else None


def list_bookings(traveler_name=None, limit=20) -> list[dict]:
    if traveler_name:
        return _query(
            "SELECT * FROM bookings WHERE LOWER(traveler_name) = LOWER(?) "
            "ORDER BY booking_date DESC LIMIT ?",
            (traveler_name.strip(), int(limit)),
        )
    return _query("SELECT * FROM bookings ORDER BY booking_date DESC LIMIT ?", (int(limit),))


def update_booking(booking_id: str, **fields) -> dict | None:
    allowed = {"item_id", "traveler_name", "status", "total_cost", "booking_type"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_booking(booking_id)
    sets = ", ".join(f"{k} = ?" for k in updates)
    with _LOCK:
        with _connect() as conn:
            cur = conn.execute(
                f"UPDATE bookings SET {sets} WHERE booking_id = ?",
                (*updates.values(), booking_id.strip()),
            )
            if cur.rowcount == 0:
                return None
    return get_booking(booking_id)


def cancel_booking(booking_id: str) -> dict | None:
    """Soft-cancel (status -> cancelled). We never hard-delete records."""
    return update_booking(booking_id, status="cancelled")
