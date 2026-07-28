"""MCP Server 2 — Travel Operations Server (streamable-http, port 8002).

Eight tools over a SQLite database seeded from CSV: flight/hotel/activity search,
trip-budget calculation, and full mock booking lifecycle (create, retrieve,
update, cancel).

All booking functionality is MOCK/DEMO. No real reservations, no payments.

Run: uv run python -m mcp_server_2.main
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from common.config import settings
from common.db import init_db
from common.logging_utils import get_logger, log_event
from mcp_server_2 import tools

logger = get_logger("mcp2")

mcp = FastMCP(
    "travel-operations",
    instructions=(
        "Search demo flight, hotel, and activity inventory; calculate and "
        "optimise trip budgets; and manage mock bookings (create / retrieve / "
        "update / cancel). All data is synthetic demo data held in SQLite — it "
        "is NOT live availability, and no booking here is real."
    ),
    host=settings.host,
    port=settings.mcp2_port,
)


# ---------------- search tools ----------------
@mcp.tool(annotations={"title": "Search Flights", "readOnlyHint": True})
def search_flights(
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    departure_date: Optional[str] = None,
    return_date: Optional[str] = None,
    max_price: Optional[float] = None,
    limit: int = 10,
) -> dict:
    """Search flights, cheapest-first.

    Depending on configuration this returns either live flight offers (from the
    Duffel API in test mode) or sample estimates. Check the `live` field in the
    result: when it is true the prices and schedules are real; when false they
    are sample estimates. Either way, do not promise a seat is held until it is
    booked, and each result's `flight_id` is the id to pass to create_booking.

    Args:
        origin: Departure city, e.g. "New York", "London", "Delhi".
        destination: Arrival city, e.g. "Tokyo", "Paris".
        departure_date: ISO date, e.g. "2026-10-05". Recommended for live search.
        return_date: ISO date for the return leg.
        max_price: Only return flights at or below this price.
        limit: Maximum rows to return (default 10).
    """
    return tools.search_flights(origin, destination, departure_date,
                                return_date, max_price, limit)


@mcp.tool(annotations={"title": "Search Hotels", "readOnlyHint": True})
def search_hotels(
    destination: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    max_price_per_night: Optional[float] = None,
    minimum_rating: Optional[float] = None,
    category: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """Search demo hotel inventory, best-rated first.

    Synthetic demo data, NOT live availability. If check_in and check_out are
    given, each result also carries `estimated_total_for_stay`.

    Args:
        destination: City name, e.g. "Tokyo", "Kyoto", "London".
        check_in: ISO date; used only to compute the number of nights.
        check_out: ISO date; used only to compute the number of nights.
        max_price_per_night: Cap on nightly rate in USD.
        minimum_rating: Minimum star rating from 0 to 5, e.g. 4.0.
        category: One of "budget", "mid-range", "luxury".
        limit: Maximum rows to return (default 10).
    """
    return tools.search_hotels(destination, check_in, check_out,
                               max_price_per_night, minimum_rating,
                               category, limit)


@mcp.tool(annotations={"title": "Search Activities", "readOnlyHint": True})
def search_activities(
    destination: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    limit: int = 10,
) -> dict:
    """Search demo activity and tour inventory, best-rated first.

    Args:
        destination: City name, e.g. "Kyoto", "Barcelona".
        category: One of "sightseeing", "food", "culture", "adventure", "leisure".
        max_price: Cap on price per person in USD.
        limit: Maximum rows to return (default 10).
    """
    return tools.search_activities(destination, category, max_price, limit)


# ---------------- budget tool ----------------
@mcp.tool(annotations={"title": "Calculate Trip Budget", "readOnlyHint": True})
def calculate_trip_budget(
    flight_cost: float = 0.0,
    hotel_cost: float = 0.0,
    food_cost: float = 0.0,
    transportation_cost: float = 0.0,
    activity_cost: float = 0.0,
    miscellaneous_cost: float = 0.0,
    target_budget: Optional[float] = None,
    travelers: int = 1,
) -> dict:
    """Total up trip cost components and compare against a target budget.

    When the total exceeds `target_budget`, the result includes ranked
    `suggested_savings` levers (lower hotel category, fewer paid activities,
    public transport, dining mix, flexible flights, shorter trip) with an
    estimated saving for each.

    Args:
        flight_cost: Total flight cost for all travelers (USD).
        hotel_cost: Total accommodation cost for the whole stay (USD).
        food_cost: Total food budget for the trip (USD).
        transportation_cost: Local and intercity transport total (USD).
        activity_cost: Total for tours, entries, and experiences (USD).
        miscellaneous_cost: Insurance, visas, shopping, buffer (USD).
        target_budget: The user's stated total budget, if any (USD).
        travelers: Number of travelers, used for per-person figures.
    """
    return tools.calculate_trip_budget(
        flight_cost, hotel_cost, food_cost, transportation_cost,
        activity_cost, miscellaneous_cost, target_budget, travelers,
    )


# ---------------- booking lifecycle (mock) ----------------
@mcp.tool(annotations={"title": "Create Booking (Mock)", "destructiveHint": False})
def create_booking(
    booking_type: str,
    item_id: str,
    traveler_name: str,
    total_cost: float,
) -> dict:
    """Create a booking.

    For flights whose id starts with "off_" (a live flight offer), this creates
    a real test-mode order with the flight provider — a genuine sandbox booking
    with an airline reference, but no payment and no real seat held. For all
    other items it records a practice booking in the sample database.

    In every case: no real money moves. Never ask the user for card, passport,
    or other sensitive details — this tool does not accept them, and uses
    fixed test passenger details for sandbox orders.

    Args:
        booking_type: One of "flight", "hotel", "activity", "package".
        item_id: The id from a search result — a flight offer id like
            "off_0000...", or a sample id like "HT0042", "AC0033".
        traveler_name: Name to record on the booking.
        total_cost: Total cost to record.
    """
    return tools.create_booking(booking_type, item_id, traveler_name, total_cost)


@mcp.tool(annotations={"title": "Retrieve Booking", "readOnlyHint": True})
def retrieve_booking(
    booking_id: Optional[str] = None,
    traveler_name: Optional[str] = None,
) -> dict:
    """Look up demo bookings by booking id, or list all bookings for a traveler.

    Args:
        booking_id: Exact booking reference, e.g. "BK-DEMO001".
        traveler_name: Traveler name to list bookings for.
    """
    return tools.retrieve_booking(booking_id, traveler_name)


@mcp.tool(annotations={"title": "Update Booking", "idempotentHint": True})
def update_booking(
    booking_id: str,
    item_id: Optional[str] = None,
    traveler_name: Optional[str] = None,
    status: Optional[str] = None,
    total_cost: Optional[float] = None,
) -> dict:
    """Modify an existing MOCK booking. Only supplied fields change.

    Args:
        booking_id: The booking to modify, e.g. "BK-DEMO001".
        item_id: New item id (e.g. moving to a different hotel).
        traveler_name: Corrected traveler name.
        status: One of "confirmed", "cancelled", "completed", "pending".
        total_cost: Revised total cost (USD).
    """
    return tools.update_booking(booking_id, item_id, traveler_name,
                                status, total_cost)


@mcp.tool(annotations={"title": "Cancel Booking", "idempotentHint": True})
def cancel_booking(booking_id: str) -> dict:
    """Cancel a MOCK booking by setting its status to "cancelled".

    The record is retained for audit rather than deleted, and no refund is
    processed (this is demo data). Mention the relevant cancellation policy when
    reporting the result.

    Args:
        booking_id: The booking to cancel, e.g. "BK-DEMO001".
    """
    return tools.cancel_booking(booking_id)


if __name__ == "__main__":
    counts = init_db()
    log_event(logger, "db_ready", **counts)
    print(f"Travel Operations MCP server on {settings.mcp2_url}")
    print(f"  seeded rows: {counts}")
    mcp.run(transport="streamable-http")
