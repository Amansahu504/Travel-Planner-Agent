"""Synthetic-database flight provider (the default).

Wraps the existing SQLite flight inventory and mock booking so the provider
interface works with zero external dependencies. This is what runs when no
Duffel key is configured.
"""
from __future__ import annotations

from common import db


class DemoFlightProvider:
    name = "demo"
    live = False

    def search_flights(self, origin=None, destination=None, departure_date=None,
                       return_date=None, max_price=None, limit=10) -> dict:
        rows = db.search_flights(origin, destination, departure_date,
                                 return_date, max_price, limit)
        for row in rows:
            row["currency"] = "USD"
            row["bookable"] = True  # via create_booking on the SQLite store
        return {
            "provider": self.name,
            "live": False,
            "count": len(rows),
            "flights": rows,
            "cheapest_price": min((r["price"] for r in rows), default=None),
            "note": ("Sample flight data — estimated prices, not live "
                     "availability. Verify before booking."),
        }

    def book_flight(self, offer_id: str, traveler_name: str,
                    total_cost: float | None = None) -> dict:
        """Book a demo flight (offer_id is a synthetic flight_id like FL0007)."""
        row = db.create_booking("flight", offer_id, traveler_name,
                                float(total_cost or 0.0))
        return {
            "status": "ok",
            "booking": row,
            "note": ("Practice booking only — recorded in the sample database. "
                     "Nothing was reserved and no payment was taken."),
        }
