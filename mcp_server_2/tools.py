"""Business logic for MCP Server 2 (travel operations).

Separated from main.py so the logic is unit-testable without a running server.
Every function validates its inputs and returns a plain dict — no exceptions
escape to the MCP layer.

IMPORTANT: all booking behaviour is mock/demo. No real reservation is made and
no payment is ever processed.
"""
from __future__ import annotations

from common import db
from common.logging_utils import get_logger, log_event
from common.providers import get_flight_provider

logger = get_logger("mcp2.tools")

DEMO_NOTE = ("Sample data from a synthetic database. Prices and availability are "
             "estimates and should be verified before booking.")

VALID_BOOKING_TYPES = {"flight", "hotel", "activity", "package"}


def _num(value, field: str, minimum: float | None = 0.0):
    """Coerce to float, raising a friendly message for bad input."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number, got {value!r}")
    if minimum is not None and out < minimum:
        raise ValueError(f"{field} must be >= {minimum}, got {out}")
    return out


def search_flights(origin=None, destination=None, departure_date=None,
                   return_date=None, max_price=None, limit=10) -> dict:
    """Search flights via the active provider (live Duffel or synthetic demo).

    On any live-provider failure this transparently falls back to the synthetic
    database so flight search never hard-fails.
    """
    try:
        max_price = _num(max_price, "max_price")
    except ValueError as exc:
        return {"error": str(exc), "count": 0, "flights": []}

    provider = get_flight_provider()
    try:
        result = provider.search_flights(origin, destination, departure_date,
                                         return_date, max_price, limit)
    except Exception as exc:
        log_event(logger, "tool_error", tool="search_flights",
                  provider=provider.name, error=str(exc))
        result = {"error": f"Flight search failed: {exc}", "count": 0, "flights": []}

    # If a live search produced nothing usable, fall back to the demo database
    # so the traveller still sees options.
    if provider.name != "demo" and (result.get("error") or result.get("count", 0) == 0):
        log_event(logger, "flight_search_fallback", reason=result.get("error", "no results"))
        from common.providers.demo import DemoFlightProvider

        fallback = DemoFlightProvider().search_flights(
            origin, destination, departure_date, return_date, max_price, limit)
        if fallback.get("count", 0) > 0:
            fallback["note"] = (
                "Live flight results weren't available for this search, so these "
                "are sample estimates instead. " + fallback["note"])
            fallback["fell_back_from"] = provider.name
            result = fallback

    log_event(logger, "tool_call", tool="search_flights", provider=result.get("provider", "?"),
              origin=origin or "-", destination=destination or "-",
              count=result.get("count", 0), live=result.get("live", False))
    return result


def search_hotels(destination=None, check_in=None, check_out=None,
                  max_price_per_night=None, minimum_rating=None,
                  category=None, limit=10) -> dict:
    try:
        max_price_per_night = _num(max_price_per_night, "max_price_per_night")
        minimum_rating = _num(minimum_rating, "minimum_rating")
        if minimum_rating is not None and minimum_rating > 5:
            return {"error": "minimum_rating must be between 0 and 5",
                    "count": 0, "hotels": []}
        rows = db.search_hotels(destination, max_price_per_night,
                                minimum_rating, category, limit)
    except ValueError as exc:
        return {"error": str(exc), "count": 0, "hotels": []}
    except Exception as exc:
        log_event(logger, "tool_error", tool="search_hotels", error=str(exc))
        return {"error": f"Hotel search failed: {exc}", "count": 0, "hotels": []}

    nights = _nights_between(check_in, check_out)
    if nights:
        for row in rows:
            row["estimated_total_for_stay"] = round(row["price_per_night"] * nights, 2)

    log_event(logger, "tool_call", tool="search_hotels",
              destination=destination or "-", count=len(rows), nights=nights or "-")
    return {
        "count": len(rows), "hotels": rows,
        "nights": nights,
        "note": DEMO_NOTE + (
            " Check-in/check-out are used only to estimate the stay total; "
            "this demo database holds no date-specific room inventory."
            if (check_in or check_out) else ""
        ),
    }


def _nights_between(check_in, check_out) -> int | None:
    if not check_in or not check_out:
        return None
    from datetime import date
    try:
        a = date.fromisoformat(str(check_in).strip())
        b = date.fromisoformat(str(check_out).strip())
    except ValueError:
        return None
    delta = (b - a).days
    return delta if delta > 0 else None


def search_activities(destination=None, category=None, max_price=None, limit=10) -> dict:
    try:
        max_price = _num(max_price, "max_price")
        rows = db.search_activities(destination, category, max_price, limit)
    except ValueError as exc:
        return {"error": str(exc), "count": 0, "activities": []}
    except Exception as exc:
        log_event(logger, "tool_error", tool="search_activities", error=str(exc))
        return {"error": f"Activity search failed: {exc}", "count": 0, "activities": []}

    log_event(logger, "tool_call", tool="search_activities",
              destination=destination or "-", count=len(rows))
    return {"count": len(rows), "activities": rows, "note": DEMO_NOTE}


def calculate_trip_budget(flight_cost=0.0, hotel_cost=0.0, food_cost=0.0,
                          transportation_cost=0.0, activity_cost=0.0,
                          miscellaneous_cost=0.0, target_budget=None,
                          travelers=1) -> dict:
    """Sum cost components and compare against an optional target budget."""
    try:
        parts = {
            "flight_cost": _num(flight_cost, "flight_cost") or 0.0,
            "hotel_cost": _num(hotel_cost, "hotel_cost") or 0.0,
            "food_cost": _num(food_cost, "food_cost") or 0.0,
            "transportation_cost": _num(transportation_cost, "transportation_cost") or 0.0,
            "activity_cost": _num(activity_cost, "activity_cost") or 0.0,
            "miscellaneous_cost": _num(miscellaneous_cost, "miscellaneous_cost") or 0.0,
        }
        target = _num(target_budget, "target_budget")
        travelers = int(_num(travelers, "travelers", minimum=1) or 1)
    except ValueError as exc:
        return {"error": str(exc)}

    total = round(sum(parts.values()), 2)
    out = {
        "breakdown": parts,
        "total_estimated_cost": total,
        "travelers": travelers,
        "per_person_cost": round(total / travelers, 2) if travelers else total,
        "note": "All figures are planning estimates from demo data, not live prices.",
    }

    if target:
        difference = round(total - target, 2)
        out.update({
            "target_budget": target,
            "difference": difference,
            "within_budget": difference <= 0,
            "status": "within budget" if difference <= 0 else "over budget",
        })
        if difference > 0:
            out["suggested_savings"] = _savings_suggestions(parts, difference)

    log_event(logger, "tool_call", tool="calculate_trip_budget",
              total=total, target=target or "-",
              within_budget=out.get("within_budget", "n/a"))
    return out


def _savings_suggestions(parts: dict, overage: float) -> list[dict]:
    """Concrete, ranked levers for closing a budget gap (spec section 13)."""
    ideas = []
    if parts["hotel_cost"] > 0:
        ideas.append({
            "lever": "Lower hotel category",
            "detail": "Move from luxury/mid-range to the next tier down, or shift "
                      "to a hotel slightly outside the centre.",
            "potential_saving": round(parts["hotel_cost"] * 0.30, 2),
        })
    if parts["activity_cost"] > 0:
        ideas.append({
            "lever": "Reduce paid activities",
            "detail": "Swap one or two paid tours for free walking routes, parks, "
                      "or free-entry museums.",
            "potential_saving": round(parts["activity_cost"] * 0.35, 2),
        })
    if parts["transportation_cost"] > 0:
        ideas.append({
            "lever": "Use public transport passes",
            "detail": "Replace taxis and private transfers with metro/rail day or "
                      "multi-day passes.",
            "potential_saving": round(parts["transportation_cost"] * 0.40, 2),
        })
    if parts["food_cost"] > 0:
        ideas.append({
            "lever": "Adjust dining mix",
            "detail": "Keep one standout meal per city and use markets, street "
                      "food, and casual spots otherwise.",
            "potential_saving": round(parts["food_cost"] * 0.25, 2),
        })
    if parts["flight_cost"] > 0:
        ideas.append({
            "lever": "Flexible flight dates or cabin",
            "detail": "Shift departure by a few days or drop to a lower cabin class.",
            "potential_saving": round(parts["flight_cost"] * 0.15, 2),
        })
    ideas.append({
        "lever": "Shorten the trip by one day",
        "detail": "Removing the least-valuable day cuts hotel, food, and local "
                  "transport for that day.",
        "potential_saving": None,
    })
    ideas.sort(key=lambda i: i["potential_saving"] or 0, reverse=True)
    return [{**i, "closes_gap": (i["potential_saving"] or 0) >= overage} for i in ideas]


# ---- booking tools (mock/demo only) ----
def create_booking(booking_type: str, item_id: str, traveler_name: str,
                   total_cost: float) -> dict:
    if not booking_type or booking_type.strip().lower() not in VALID_BOOKING_TYPES:
        return {"status": "error",
                "error": f"booking_type must be one of {sorted(VALID_BOOKING_TYPES)}"}
    if not item_id or not str(item_id).strip():
        return {"status": "error", "error": "item_id is required"}
    if not traveler_name or not str(traveler_name).strip():
        return {"status": "error", "error": "traveler_name is required"}
    try:
        cost = _num(total_cost, "total_cost") or 0.0
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}

    btype = booking_type.strip().lower()
    item = str(item_id).strip()

    # A Duffel offer id routes to real (test-mode) flight booking; everything
    # else is a synthetic-database record.
    if btype == "flight" and item.startswith("off_"):
        provider = get_flight_provider()
        book = getattr(provider, "book_flight", None)
        if book is not None:
            result = book(item, str(traveler_name).strip(), cost)
            log_event(logger, "tool_call", tool="create_booking",
                      provider=provider.name, booking_type="flight",
                      status=result.get("status"))
            if result.get("status") == "ok":
                result["action"] = "created"
            return result

    try:
        row = db.create_booking(btype, item, str(traveler_name).strip(), cost)
    except Exception as exc:
        log_event(logger, "tool_error", tool="create_booking", error=str(exc))
        return {"status": "error", "error": f"Booking failed: {exc}"}

    log_event(logger, "tool_call", tool="create_booking",
              booking_id=row["booking_id"], booking_type=btype)
    return {
        "status": "ok", "action": "created", "booking": row,
        "note": "Practice booking — recorded in the sample database only. Nothing "
                "was reserved and no payment was taken.",
    }


def retrieve_booking(booking_id: str | None = None,
                     traveler_name: str | None = None) -> dict:
    if not booking_id and not traveler_name:
        return {"error": "Provide either booking_id or traveler_name.",
                "count": 0, "bookings": []}
    try:
        if booking_id:
            row = db.get_booking(booking_id)
            if not row:
                return {"count": 0, "bookings": [],
                        "message": f"No booking found with id '{booking_id}'."}
            return {"count": 1, "bookings": [row]}
        rows = db.list_bookings(traveler_name)
    except Exception as exc:
        log_event(logger, "tool_error", tool="retrieve_booking", error=str(exc))
        return {"error": f"Retrieval failed: {exc}", "count": 0, "bookings": []}

    log_event(logger, "tool_call", tool="retrieve_booking", count=len(rows))
    if not rows:
        return {"count": 0, "bookings": [],
                "message": f"No bookings found for '{traveler_name}'."}
    return {"count": len(rows), "bookings": rows}


def update_booking(booking_id: str, item_id=None, traveler_name=None,
                   status=None, total_cost=None) -> dict:
    if not booking_id or not str(booking_id).strip():
        return {"status": "error", "error": "booking_id is required"}
    if status is not None and str(status).strip().lower() not in {
        "confirmed", "cancelled", "completed", "pending"
    }:
        return {"status": "error",
                "error": "status must be one of: confirmed, cancelled, completed, pending"}
    try:
        cost = _num(total_cost, "total_cost")
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}

    try:
        row = db.update_booking(
            booking_id, item_id=item_id, traveler_name=traveler_name,
            status=(status.strip().lower() if status else None), total_cost=cost,
        )
    except Exception as exc:
        log_event(logger, "tool_error", tool="update_booking", error=str(exc))
        return {"status": "error", "error": f"Update failed: {exc}"}

    if row is None:
        return {"status": "error",
                "error": f"No booking found with id '{booking_id}'."}
    log_event(logger, "tool_call", tool="update_booking", booking_id=booking_id)
    return {"status": "ok", "action": "updated", "booking": row,
            "note": "Mock/demo booking record updated."}


def cancel_booking(booking_id: str) -> dict:
    if not booking_id or not str(booking_id).strip():
        return {"status": "error", "error": "booking_id is required"}
    try:
        existing = db.get_booking(booking_id)
        if not existing:
            return {"status": "error",
                    "error": f"No booking found with id '{booking_id}'."}
        if existing["status"] == "cancelled":
            return {"status": "ok", "action": "already_cancelled",
                    "booking": existing}
        row = db.cancel_booking(booking_id)
    except Exception as exc:
        log_event(logger, "tool_error", tool="cancel_booking", error=str(exc))
        return {"status": "error", "error": f"Cancellation failed: {exc}"}

    log_event(logger, "tool_call", tool="cancel_booking", booking_id=booking_id)
    return {
        "status": "ok", "action": "cancelled", "booking": row,
        "note": "Mock cancellation: status set to 'cancelled'. The record is "
                "retained for audit and no refund was processed (demo only). "
                "See the hotel/flight cancellation demo policies for terms.",
    }
