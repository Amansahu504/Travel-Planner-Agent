"""Pluggable flight providers.

The synthetic database is the default and needs no external service. When a
Duffel test-mode key is configured, flight search and booking use the live
Duffel API instead — behind the exact same interface, so nothing else in the
system changes.

    from common.providers import get_flight_provider
    provider = get_flight_provider()
    provider.search_flights(origin="London", destination="New York", ...)
"""
from __future__ import annotations

from common.config import settings
from common.providers.base import FlightProvider

_provider: FlightProvider | None = None


def get_flight_provider() -> FlightProvider:
    """Return the active flight provider (cached).

    Duffel when `use_duffel_flights` is true and the client imports cleanly,
    otherwise the synthetic-database provider. Never raises — a Duffel import or
    construction failure degrades to demo rather than breaking flight tools.
    """
    global _provider
    if _provider is not None:
        return _provider

    if settings.use_duffel_flights:
        try:
            from common.providers.duffel import DuffelFlightProvider

            _provider = DuffelFlightProvider()
            return _provider
        except Exception as exc:  # missing key, import error, etc.
            from common.logging_utils import get_logger, log_event

            log_event(get_logger("providers"), "duffel_unavailable",
                      error=str(exc), fallback="demo")

    from common.providers.demo import DemoFlightProvider

    _provider = DemoFlightProvider()
    return _provider


def reset_provider_cache() -> None:
    """Test hook: forget the cached provider so settings changes take effect."""
    global _provider
    _provider = None
