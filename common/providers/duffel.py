"""Live Duffel flight provider (test mode).

Talks to the real Duffel API. In test mode the offers are real airline
schedules but bookings are sandbox orders — no money moves and no real seat is
held. Requires a `duffel_test_...` key in DUFFEL_API_KEY.

Flow:
  search_flights  -> POST /air/offer_requests?return_offers=true
  book_flight     -> POST /air/orders  (balance payment, test passenger)

Booking uses clearly-synthetic test passenger details (a demo name plus fixed
placeholder contact/DOB). No real personal data is collected or transmitted;
this is a sandbox only.
"""
from __future__ import annotations

from datetime import date, timedelta

import httpx

from common.config import settings
from common.db import create_booking as record_booking
from common.logging_utils import get_logger, log_event
from common.providers.airports import to_city, to_iata

logger = get_logger("providers.duffel")

BASE_URL = "https://api.duffel.com"
# Test passenger placeholders — obviously fake, used only in the sandbox.
TEST_EMAIL = "demo.traveller@example.com"
TEST_PHONE = "+442080160509"
TEST_DOB = "1990-01-01"


class DuffelConfigError(RuntimeError):
    pass


class DuffelFlightProvider:
    name = "duffel"
    live = True

    def __init__(self) -> None:
        if not settings.duffel_configured:
            raise DuffelConfigError("DUFFEL_API_KEY is missing or not a duffel_ key")
        self._key = settings.duffel_api_key
        self._version = settings.duffel_version
        self._test_mode = self._key.startswith("duffel_test_")

    # ---- http ----
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._key}",
            "Duffel-Version": self._version,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict, params: dict | None = None) -> httpx.Response:
        with httpx.Client(timeout=60) as client:
            return client.post(BASE_URL + path, headers=self._headers(),
                               json=body, params=params or {})

    def _get(self, path: str) -> httpx.Response:
        with httpx.Client(timeout=30) as client:
            return client.get(BASE_URL + path, headers=self._headers())

    @staticmethod
    def _duffel_error(resp: httpx.Response) -> str:
        try:
            errors = resp.json().get("errors", [])
            if errors:
                first = errors[0]
                return first.get("message") or first.get("title") or str(first)
        except Exception:
            pass
        return f"HTTP {resp.status_code}"

    # ---- search ----
    def search_flights(self, origin=None, destination=None, departure_date=None,
                       return_date=None, max_price=None, limit=10) -> dict:
        origin_iata = to_iata(origin)
        dest_iata = to_iata(destination)

        # Duffel requires both endpoints and a departure date.
        if not origin_iata or not dest_iata:
            return self._search_error(
                origin, destination,
                "Live flight search needs both a departure and arrival city that "
                "map to an airport. Try well-known cities, e.g. 'London' to "
                "'Tokyo'.",
            )

        if not departure_date:
            # Default to ~30 days out so a search without a date still works.
            departure_date = (date.today() + timedelta(days=30)).isoformat()
            assumed_date = True
        else:
            assumed_date = False

        slices = [{"origin": origin_iata, "destination": dest_iata,
                   "departure_date": departure_date}]
        if return_date:
            slices.append({"origin": dest_iata, "destination": origin_iata,
                           "departure_date": return_date})

        body = {"data": {"slices": slices, "passengers": [{"type": "adult"}],
                         "cabin_class": "economy"}}

        try:
            resp = self._post("/air/offer_requests", body,
                              params={"return_offers": "true",
                                      "supplier_timeout": "15000"})
        except Exception as exc:
            log_event(logger, "duffel_search_failed", error=str(exc))
            return self._search_error(origin, destination,
                                      f"Could not reach the flight service: {exc}")

        if resp.status_code >= 300:
            msg = self._duffel_error(resp)
            log_event(logger, "duffel_search_rejected", status=resp.status_code,
                      error=msg)
            return self._search_error(origin, destination, msg)

        offers = resp.json().get("data", {}).get("offers", [])
        flights = [self._map_offer(o) for o in offers]

        if max_price is not None:
            flights = [f for f in flights if f["price"] <= float(max_price)]
        flights.sort(key=lambda f: f["price"])
        flights = flights[: max(1, int(limit))]

        note = ("Live flight offers from the Duffel API"
                + (" (test mode — real schedules, sandbox prices, not payable)"
                   if self._test_mode else "")
                + ". Confirm details before booking.")
        if assumed_date:
            note += f" No date was given, so results are for {departure_date}."

        log_event(logger, "duffel_search", origin=origin_iata, dest=dest_iata,
                  offers=len(offers), returned=len(flights))

        return {
            "provider": self.name,
            "live": True,
            "test_mode": self._test_mode,
            "count": len(flights),
            "flights": flights,
            "cheapest_price": min((f["price"] for f in flights), default=None),
            "note": note,
        }

    def _search_error(self, origin, destination, message: str) -> dict:
        return {
            "provider": self.name, "live": True, "count": 0, "flights": [],
            "cheapest_price": None,
            "error": message,
            "note": "Live flight search was unavailable for this query.",
        }

    def _map_offer(self, offer: dict) -> dict:
        """Map a Duffel offer to the shared flight shape.

        flight_id is the Duffel offer id so book_flight can reference it.
        """
        first_slice = offer["slices"][0]
        segments = first_slice.get("segments", [])
        first_seg = segments[0] if segments else {}
        last_slice = offer["slices"][-1]

        origin_code = first_slice.get("origin", {}).get("iata_code")
        dest_code = first_slice.get("destination", {}).get("iata_code")

        # departure date from the first segment's timestamp
        dep = (first_seg.get("departing_at") or "")[:10]
        ret = None
        if len(offer["slices"]) > 1:
            ret_segs = last_slice.get("segments", [])
            if ret_segs:
                ret = (ret_segs[0].get("departing_at") or "")[:10]

        cabin = "economy"
        if first_seg.get("passengers"):
            cabin = first_seg["passengers"][0].get("cabin_class") or "economy"

        return {
            "flight_id": offer["id"],                 # off_... -> used to book
            "airline": offer.get("owner", {}).get("name", "Unknown"),
            "origin": to_city(origin_code),
            "destination": to_city(dest_code),
            "origin_code": origin_code,
            "destination_code": dest_code,
            "departure_date": dep,
            "return_date": ret,
            "price": round(float(offer["total_amount"]), 2),
            "currency": offer.get("total_currency", "USD"),
            "available_seats": None,       # Duffel doesn't expose a raw seat count
            "class": cabin,
            "stops": max(0, len(segments) - 1),
            "bookable": True,
            "expires_at": offer.get("expires_at"),
        }

    # ---- booking ----
    def book_flight(self, offer_id: str, traveler_name: str,
                    total_cost: float | None = None) -> dict:
        """Create a real Duffel test order from an offer id."""
        if not offer_id or not offer_id.startswith("off_"):
            return {"status": "error",
                    "error": "A Duffel offer id (starting 'off_') is required. "
                             "Search for flights first, then book a specific offer."}

        # Re-fetch the offer to get its live price + passenger id (offers expire).
        try:
            offer_resp = self._get(f"/air/offers/{offer_id}?return_available_services=false")
        except Exception as exc:
            return {"status": "error", "error": f"Could not reach flight service: {exc}"}

        if offer_resp.status_code >= 300:
            msg = self._duffel_error(offer_resp)
            if offer_resp.status_code in (404, 410, 422):
                msg = ("That flight offer has expired. Please search again and "
                       "book from the fresh results.")
            return {"status": "error", "error": msg}

        offer = offer_resp.json()["data"]
        amount = offer["total_amount"]
        currency = offer["total_currency"]
        passenger_id = offer["passengers"][0]["id"]

        given, family = self._split_name(traveler_name)
        order_body = {"data": {
            "type": "instant",
            "selected_offers": [offer_id],
            "payments": [{"type": "balance", "amount": amount, "currency": currency}],
            "passengers": [{
                "id": passenger_id, "type": "adult", "title": "mr",
                "given_name": given, "family_name": family,
                "gender": "m", "born_on": TEST_DOB,
                "email": TEST_EMAIL, "phone_number": TEST_PHONE,
            }],
        }}

        try:
            resp = self._post("/air/orders", order_body)
        except Exception as exc:
            return {"status": "error", "error": f"Could not reach flight service: {exc}"}

        if resp.status_code >= 300:
            msg = self._duffel_error(resp)
            log_event(logger, "duffel_order_rejected", status=resp.status_code,
                      error=msg)
            return {"status": "error", "error": msg}

        order = resp.json()["data"]
        reference = order.get("booking_reference")
        order_id = order["id"]

        # Mirror into our SQLite store so retrieve/cancel work uniformly. We
        # store the Duffel order id as item_id so it can be cancelled later.
        local = record_booking("flight", order_id, traveler_name.strip(),
                               round(float(amount), 2))

        log_event(logger, "duffel_order_created", reference=reference,
                  order_id=order_id, booking_id=local["booking_id"])

        return {
            "status": "ok",
            "booking": {
                **local,
                "airline_booking_reference": reference,
                "duffel_order_id": order_id,
                "currency": currency,
                "passenger": f"{given} {family}",
                "live": True,
                "test_mode": self._test_mode,
            },
            "note": ("Test-mode flight booking created with the Duffel API. This "
                     "is a real sandbox order (reference "
                     f"{reference}) but no payment was taken and no real seat is "
                     "held. Use a real booking channel for actual travel."),
        }

    @staticmethod
    def _split_name(full: str) -> tuple[str, str]:
        parts = (full or "").strip().split()
        if not parts:
            return "Demo", "Traveller"
        if len(parts) == 1:
            return parts[0], "Traveller"
        return parts[0], " ".join(parts[1:])

    # ---- optional: cancel a Duffel order ----
    def cancel_order(self, order_id: str) -> dict:
        """Cancel a Duffel test order (create + confirm cancellation)."""
        try:
            create = self._post("/air/order_cancellations",
                                {"data": {"order_id": order_id}})
            if create.status_code >= 300:
                return {"status": "error", "error": self._duffel_error(create)}
            cancellation_id = create.json()["data"]["id"]
            confirm = self._post(
                f"/air/order_cancellations/{cancellation_id}/actions/confirm", {}
            )
            if confirm.status_code >= 300:
                return {"status": "error", "error": self._duffel_error(confirm)}
            return {"status": "ok", "order_id": order_id,
                    "note": "Duffel test order cancelled."}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
