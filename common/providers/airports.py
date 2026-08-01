"""City name → IATA airport code mapping.

The synthetic database keys on city names ("Tokyo", "New York"); Duffel needs
IATA codes ("HND", "JFK"). This maps every destination and origin hub the demo
knows about, and falls back to treating an already-3-letter input as a code.
"""
from __future__ import annotations

# Primary airport for each city the system knows. Where a city has several, the
# main international airport is chosen.
CITY_TO_IATA: dict[str, str] = {
    # destinations
    "tokyo": "HND",
    "kyoto": "KIX",        # nearest major airport (Kansai / Osaka)
    "osaka": "KIX",
    "paris": "CDG",
    "nice": "NCE",
    "london": "LHR",
    "edinburgh": "EDI",
    "new york": "JFK",
    "san francisco": "SFO",
    "rome": "FCO",
    "venice": "VCE",
    "barcelona": "BCN",
    "madrid": "MAD",
    "singapore": "SIN",
    "bangkok": "BKK",
    "phuket": "HKT",
    "sydney": "SYD",
    "melbourne": "MEL",
    "dubai": "DXB",
    "abu dhabi": "AUH",
    "delhi": "DEL",
    "jaipur": "JAI",
    "mumbai": "BOM",
    # additional origin hubs
    "los angeles": "LAX",
    "chicago": "ORD",
    "toronto": "YYZ",
    "frankfurt": "FRA",
    "amsterdam": "AMS",
    "hong kong": "HKG",
    "doha": "DOH",
    "istanbul": "IST",
}

IATA_TO_CITY = {code: city.title() for city, code in CITY_TO_IATA.items()}


def to_iata(place: str | None) -> str | None:
    """Resolve a city name (or existing IATA code) to an IATA code.

    Returns None when the input is empty or can't be resolved to something that
    looks like a code.
    """
    if not place:
        return None
    key = place.strip().lower()
    if key in CITY_TO_IATA:
        return CITY_TO_IATA[key]
    # Already an airport/city code?
    compact = place.strip().upper()
    if len(compact) == 3 and compact.isalpha():
        return compact
    return None


def to_city(iata: str | None) -> str:
    """Human label for an IATA code, or the code itself if unknown."""
    if not iata:
        return ""
    return IATA_TO_CITY.get(iata.strip().upper(), iata.strip().upper())
