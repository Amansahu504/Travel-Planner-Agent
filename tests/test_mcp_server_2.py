"""Tests for MCP Server 2 — travel operations (search, budget, bookings).

The tool logic is tested directly against the SQLite database (no server needed),
plus one test over a live MCP connection to prove the transport works.
"""
from __future__ import annotations

import json

import pytest

from common import db
from common.config import settings
from mcp_server_2 import tools
from tests.conftest import requires_mcp2


@pytest.fixture(autouse=True)
def _force_demo_flights(monkeypatch):
    """These tests target the synthetic flight database, so pin the demo provider.

    Otherwise, when a Duffel key is present in .env, `search_flights` would make
    live network calls and the assertions about specific sample rows wouldn't
    hold. Live-provider behaviour is covered in test_providers.py.
    """
    from common import providers
    from common.providers.demo import DemoFlightProvider

    monkeypatch.setattr(providers, "_provider", DemoFlightProvider())
    yield
    providers.reset_provider_cache()


# ---------------- flight search ----------------
def test_search_flights_returns_results():
    result = tools.search_flights(destination="Tokyo")
    assert result["count"] > 0
    assert all(f["destination"] == "Tokyo" for f in result["flights"])


def test_search_flights_sorted_cheapest_first():
    result = tools.search_flights(destination="Paris", limit=10)
    prices = [f["price"] for f in result["flights"]]
    assert prices == sorted(prices)


def test_search_flights_respects_max_price():
    result = tools.search_flights(destination="Rome", max_price=500)
    assert all(f["price"] <= 500 for f in result["flights"])


def test_search_flights_origin_and_destination():
    result = tools.search_flights(origin="New York", destination="Tokyo")
    assert result["count"] >= 1
    for flight in result["flights"]:
        assert flight["origin"] == "New York"
        assert flight["destination"] == "Tokyo"


def test_search_flights_unknown_destination_is_empty_not_error():
    result = tools.search_flights(destination="Atlantis")
    assert result["count"] == 0
    assert result["flights"] == []
    assert "error" not in result


def test_search_flights_rejects_bad_price():
    result = tools.search_flights(destination="Tokyo", max_price="cheap")
    assert "error" in result
    assert result["count"] == 0


# ---------------- hotel search ----------------
def test_search_hotels_filters_price_and_rating():
    result = tools.search_hotels(destination="Tokyo", max_price_per_night=150,
                                 minimum_rating=4.0)
    assert result["count"] >= 1, "every destination should have a value mid-range room"
    for hotel in result["hotels"]:
        assert hotel["price_per_night"] <= 150
        assert hotel["rating"] >= 4.0


def test_search_hotels_category_filter():
    result = tools.search_hotels(destination="Paris", category="luxury")
    assert result["count"] > 0
    assert all(h["category"] == "luxury" for h in result["hotels"])


def test_search_hotels_computes_stay_total():
    result = tools.search_hotels(destination="Kyoto", check_in="2026-10-05",
                                 check_out="2026-10-10")
    assert result["nights"] == 5
    for hotel in result["hotels"]:
        expected = round(hotel["price_per_night"] * 5, 2)
        assert hotel["estimated_total_for_stay"] == expected


def test_search_hotels_ignores_invalid_dates():
    result = tools.search_hotels(destination="Kyoto", check_in="not-a-date",
                                 check_out="also-bad")
    assert result["nights"] is None


def test_search_hotels_rejects_rating_above_five():
    result = tools.search_hotels(destination="Tokyo", minimum_rating=9)
    assert "error" in result


# ---------------- activity search ----------------
def test_search_activities_by_category():
    result = tools.search_activities(destination="Kyoto", category="culture")
    assert result["count"] > 0
    assert all(a["category"] == "culture" for a in result["activities"])


def test_search_activities_sorted_by_rating():
    result = tools.search_activities(destination="Bangkok")
    ratings = [a["rating"] for a in result["activities"]]
    assert ratings == sorted(ratings, reverse=True)


# ---------------- budget ----------------
def test_calculate_trip_budget_totals_components():
    result = tools.calculate_trip_budget(
        flight_cost=1800, hotel_cost=1100, food_cost=500,
        transportation_cost=200, activity_cost=300, miscellaneous_cost=100,
    )
    assert result["total_estimated_cost"] == 4000.0


def test_calculate_trip_budget_detects_over_budget():
    result = tools.calculate_trip_budget(
        flight_cost=2000, hotel_cost=1450, target_budget=3000,
    )
    assert result["within_budget"] is False
    assert result["difference"] == 450.0
    assert result["status"] == "over budget"
    assert result["suggested_savings"], "over-budget results must suggest savings"


def test_calculate_trip_budget_savings_are_ranked():
    result = tools.calculate_trip_budget(
        flight_cost=1000, hotel_cost=1500, food_cost=600,
        transportation_cost=300, activity_cost=400, target_budget=2000,
    )
    savings = [s["potential_saving"] or 0 for s in result["suggested_savings"]]
    assert savings == sorted(savings, reverse=True)


def test_calculate_trip_budget_within_budget():
    result = tools.calculate_trip_budget(hotel_cost=500, target_budget=3000)
    assert result["within_budget"] is True
    assert "suggested_savings" not in result


def test_calculate_trip_budget_per_person():
    result = tools.calculate_trip_budget(hotel_cost=1000, travelers=4)
    assert result["per_person_cost"] == 250.0


def test_calculate_trip_budget_rejects_bad_input():
    result = tools.calculate_trip_budget(flight_cost="lots")
    assert "error" in result


# ---------------- booking lifecycle ----------------
def test_create_and_retrieve_booking():
    created = tools.create_booking("hotel", "HT0002", "Pytest Create", 355.5)
    assert created["status"] == "ok"
    booking_id = created["booking"]["booking_id"]
    assert "no payment was taken" in created["note"].lower()

    fetched = tools.retrieve_booking(booking_id=booking_id)
    assert fetched["count"] == 1
    assert fetched["bookings"][0]["traveler_name"] == "Pytest Create"

    db.cancel_booking(booking_id)


def test_create_booking_validates_type():
    result = tools.create_booking("teleport", "X1", "Nobody", 10)
    assert result["status"] == "error"


def test_create_booking_requires_traveler():
    result = tools.create_booking("hotel", "HT0001", "", 100)
    assert result["status"] == "error"


def test_retrieve_booking_requires_an_argument():
    result = tools.retrieve_booking()
    assert "error" in result


def test_retrieve_unknown_booking_reports_message():
    result = tools.retrieve_booking(booking_id="BK-DOES-NOT-EXIST")
    assert result["count"] == 0
    assert "message" in result


def test_update_booking_changes_fields(sample_booking):
    booking_id = sample_booking["booking_id"]
    result = tools.update_booking(booking_id, total_cost=777.0, status="pending")
    assert result["status"] == "ok"
    assert result["booking"]["total_cost"] == 777.0
    assert result["booking"]["status"] == "pending"


def test_update_booking_rejects_bad_status(sample_booking):
    result = tools.update_booking(sample_booking["booking_id"], status="teleported")
    assert result["status"] == "error"


def test_update_unknown_booking_errors():
    result = tools.update_booking("BK-NOPE", status="confirmed")
    assert result["status"] == "error"


def test_cancel_booking_soft_deletes():
    created = tools.create_booking("activity", "AC0001", "Pytest Cancel", 40)
    booking_id = created["booking"]["booking_id"]

    result = tools.cancel_booking(booking_id)
    assert result["status"] == "ok"
    assert result["booking"]["status"] == "cancelled"

    # Record is retained, never hard-deleted.
    still_there = tools.retrieve_booking(booking_id=booking_id)
    assert still_there["count"] == 1


def test_cancel_booking_is_idempotent():
    created = tools.create_booking("activity", "AC0002", "Pytest Twice", 40)
    booking_id = created["booking"]["booking_id"]
    tools.cancel_booking(booking_id)
    second = tools.cancel_booking(booking_id)
    assert second["action"] == "already_cancelled"


def test_cancel_unknown_booking_errors():
    result = tools.cancel_booking("BK-GHOST")
    assert result["status"] == "error"


# ---------------- live MCP transport ----------------
@requires_mcp2
@pytest.mark.asyncio
async def test_tools_reachable_over_streamable_http():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(settings.mcp2_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert {
                "search_flights", "search_hotels", "search_activities",
                "calculate_trip_budget", "create_booking", "retrieve_booking",
                "update_booking", "cancel_booking",
            } <= names

            result = await session.call_tool(
                "search_hotels", {"destination": "Tokyo", "max_price_per_night": 150}
            )
            payload = json.loads(result.content[0].text)
            assert payload["count"] > 0
