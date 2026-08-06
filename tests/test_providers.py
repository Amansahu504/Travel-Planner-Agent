"""Tests for the flight provider layer (demo + live Duffel).

Airport mapping, provider selection, and the demo provider run offline. The
live Duffel tests hit the real API and skip themselves unless a Duffel key is
configured.
"""
from __future__ import annotations

import pytest

from common.config import settings
from common.providers import airports, get_flight_provider, reset_provider_cache
from common.providers.demo import DemoFlightProvider

requires_duffel = pytest.mark.skipif(
    not settings.duffel_configured,
    reason="DUFFEL_API_KEY not configured",
)


@pytest.fixture(autouse=True)
def _clean_provider_cache():
    reset_provider_cache()
    yield
    reset_provider_cache()


# ---------------- airport mapping ----------------
@pytest.mark.parametrize("city,code", [
    ("Tokyo", "HND"), ("London", "LHR"), ("New York", "JFK"),
    ("Paris", "CDG"), ("Rome", "FCO"), ("Delhi", "DEL"), ("Dubai", "DXB"),
])
def test_city_maps_to_iata(city, code):
    assert airports.to_iata(city) == code


def test_iata_passthrough():
    assert airports.to_iata("SFO") == "SFO"
    assert airports.to_iata("sfo") == "SFO"


def test_unknown_place_returns_none():
    assert airports.to_iata("Atlantis") is None
    assert airports.to_iata("") is None
    assert airports.to_iata(None) is None


def test_to_city_reverses_known_codes():
    assert airports.to_city("HND") == "Tokyo"
    assert airports.to_city("JFK") == "New York"


def test_to_city_falls_back_to_code():
    assert airports.to_city("ZZZ") == "ZZZ"


# ---------------- provider selection ----------------
# `settings` is a frozen dataclass, so selection logic is tested by constructing
# fresh Settings instances (for the pure logic) and by swapping the module-level
# settings object get_flight_provider reads (for the factory).
from common.config import Settings


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_demo_forced_selects_demo(monkeypatch):
    monkeypatch.setattr("common.providers.settings",
                        _settings(flight_provider="demo",
                                  duffel_api_key="duffel_test_abc"))
    reset_provider_cache()
    assert get_flight_provider().name == "demo"


def test_auto_without_key_selects_demo(monkeypatch):
    monkeypatch.setattr("common.providers.settings",
                        _settings(flight_provider="auto", duffel_api_key=""))
    reset_provider_cache()
    provider = get_flight_provider()
    assert provider.name == "demo"
    assert provider.live is False


def test_use_duffel_flights_flag():
    assert _settings(duffel_api_key="duffel_test_abc",
                     flight_provider="auto").use_duffel_flights is True
    assert _settings(duffel_api_key="duffel_test_abc",
                     flight_provider="demo").use_duffel_flights is False
    assert _settings(duffel_api_key="",
                     flight_provider="auto").use_duffel_flights is False
    # "duffel" forces it on even without a key (construction will then fail
    # and the factory falls back to demo — see get_flight_provider).
    assert _settings(duffel_api_key="",
                     flight_provider="duffel").use_duffel_flights is True


def test_duffel_configured_rejects_placeholder():
    assert _settings(duffel_api_key="your_duffel_test_key_here").duffel_configured is False
    assert _settings(duffel_api_key="").duffel_configured is False
    assert _settings(duffel_api_key="duffel_test_real").duffel_configured is True


def test_forcing_duffel_without_key_falls_back_to_demo(monkeypatch):
    """flight_provider=duffel but no valid key must not crash — degrade to demo."""
    import common.providers.duffel as duffel_mod

    keyless = _settings(flight_provider="duffel", duffel_api_key="")
    monkeypatch.setattr("common.providers.settings", keyless)
    # The Duffel constructor reads its own module-level settings, so patch that
    # too — otherwise it sees the real key from .env and constructs fine.
    monkeypatch.setattr(duffel_mod, "settings", keyless)
    reset_provider_cache()
    assert get_flight_provider().name == "demo"


# ---------------- demo provider ----------------
def test_demo_provider_search_shape():
    result = DemoFlightProvider().search_flights(destination="Tokyo", limit=3)
    assert result["provider"] == "demo"
    assert result["live"] is False
    assert result["count"] >= 1
    for flight in result["flights"]:
        assert flight["currency"] == "USD"
        assert flight["bookable"] is True
        assert flight["destination"] == "Tokyo"


def test_demo_provider_book_creates_record():
    from common import db

    result = DemoFlightProvider().book_flight("FL0001", "Provider Test", 300.0)
    assert result["status"] == "ok"
    booking_id = result["booking"]["booking_id"]
    assert db.get_booking(booking_id) is not None
    db.cancel_booking(booking_id)


# ---------------- live Duffel ----------------
@requires_duffel
def test_duffel_provider_constructs():
    from common.providers.duffel import DuffelFlightProvider

    provider = DuffelFlightProvider()
    assert provider.name == "duffel"
    assert provider.live is True


@requires_duffel
def test_duffel_search_returns_live_offers():
    from common.providers.duffel import DuffelFlightProvider

    result = DuffelFlightProvider().search_flights(
        origin="London", destination="New York",
        departure_date="2026-11-10", limit=3,
    )
    assert result["live"] is True
    assert result["count"] >= 1
    for flight in result["flights"]:
        assert flight["flight_id"].startswith("off_")
        assert flight["price"] > 0
        assert flight["currency"]
        assert flight["airline"]


@requires_duffel
def test_duffel_search_needs_resolvable_airports():
    from common.providers.duffel import DuffelFlightProvider

    result = DuffelFlightProvider().search_flights(
        origin="Atlantis", destination="Narnia", departure_date="2026-11-10",
    )
    assert result["count"] == 0
    assert "error" in result


@requires_duffel
def test_duffel_book_rejects_non_offer_id():
    from common.providers.duffel import DuffelFlightProvider

    result = DuffelFlightProvider().book_flight("FL0001", "Someone", 100)
    assert result["status"] == "error"
    assert "offer" in result["error"].lower()


@requires_duffel
def test_duffel_full_search_and_book_roundtrip():
    """The headline capability: live search then a real test-mode booking."""
    from common.providers.duffel import DuffelFlightProvider
    from common import db

    provider = DuffelFlightProvider()
    search = provider.search_flights(origin="London", destination="New York",
                                     departure_date="2026-11-12", limit=1)
    assert search["count"] == 1
    offer_id = search["flights"][0]["flight_id"]

    booking = provider.book_flight(offer_id, "Pytest Traveller",
                                   search["flights"][0]["price"])
    assert booking["status"] == "ok", booking.get("error")
    info = booking["booking"]
    assert info["airline_booking_reference"]
    assert info["duffel_order_id"].startswith("ord_")
    assert info["live"] is True

    # Mirrored into the local store so retrieve/cancel work uniformly.
    assert db.get_booking(info["booking_id"]) is not None
    db.cancel_booking(info["booking_id"])


# ---------------- tool-level fallback ----------------
@requires_duffel
def test_tool_falls_back_to_demo_on_unresolvable_route():
    """A live search that can't resolve airports still yields sample options."""
    from mcp_server_2 import tools

    reset_provider_cache()
    # Destination-only search: Duffel can't run it (no origin), so the tool
    # should fall back to the synthetic database rather than error out.
    result = tools.search_flights(destination="Tokyo", limit=3)
    assert result["count"] >= 1
