"""Flight provider interface + shared result shape.

Both providers return the same dict shapes so MCP Server 2's tools and the Agno
agent never need to know which one is active.

search_flights -> {
    "provider": "demo" | "duffel",
    "count": int,
    "flights": [ {flight_id, airline, origin, destination, departure_date,
                  return_date, price, currency, available_seats, class,
                  bookable, ...} ],
    "cheapest_price": float | None,
    "live": bool,          # True only for real live data
    "note": str,
    "error": str | None,   # present only on failure
}

book_flight -> {
    "status": "ok" | "error",
    "booking": { ... } | None,
    "note": str,
    "error": str | None,
}
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FlightProvider(Protocol):
    name: str
    live: bool  # True when results are real live data, not synthetic

    def search_flights(
        self,
        origin: str | None = None,
        destination: str | None = None,
        departure_date: str | None = None,
        return_date: str | None = None,
        max_price: float | None = None,
        limit: int = 10,
    ) -> dict:
        ...

    def book_flight(
        self,
        offer_id: str,
        traveler_name: str,
        total_cost: float | None = None,
    ) -> dict:
        ...
