"""Generate all synthetic demo data for the travel ecosystem.

Produces (spec section 18):
  * data/knowledge/*.md      - destination knowledge docs (>= 100 records)
  * data/seed/flights.csv    - >= 100 flights
  * data/seed/hotels.csv     - >= 100 hotels
  * data/seed/activities.csv - >= 100 activities
  * data/seed/bookings.csv   - >= 50 bookings

Everything here is SYNTHETIC DEMO DATA. Prices, availability, and traveler
names are fabricated for demonstration and contain no real personal data.

Run: uv run python -m scripts.generate_data
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta

from common.config import (
    KNOWLEDGE_DIR, SEED_DIR, FLIGHTS_CSV, HOTELS_CSV, ACTIVITIES_CSV, BOOKINGS_CSV,
)
from common.db import COLUMNS
from scripts.destinations import (
    AIRLINES, DESTINATIONS, HOTEL_CATEGORIES, ORIGIN_HUBS,
)

SEED = 20251025
DEMO_BANNER = (
    "> **DEMO DATA.** This document is synthetic content written for a "
    "demonstration project. Verify all details independently before travelling."
)

# Fabricated traveler names for demo bookings (not real people).
DEMO_TRAVELERS = [
    "Demo Traveler A", "Demo Traveler B", "Demo Traveler C", "Demo Traveler D",
    "Demo Traveler E", "Demo Traveler F", "Demo Traveler G", "Demo Traveler H",
    "Sample Guest 1", "Sample Guest 2", "Sample Guest 3", "Sample Guest 4",
]

HOTEL_NAME_PARTS = {
    "budget": ["Backpacker Lodge", "City Hostel", "Budget Inn", "Traveler's Rest", "Value Stay"],
    "mid-range": ["Central Hotel", "Garden Hotel", "Riverside Hotel", "Plaza Hotel", "Boutique House"],
    "luxury": ["Grand Palace Hotel", "Skyline Resort", "Heritage Grand", "Luxury Collection", "Royal Suites"],
}

PRICE_BANDS = {  # per-night USD band per category, scaled by destination tier
    "budget": (35, 90),
    "mid-range": (95, 200),
    "luxury": (240, 620),
}

# Rough cost tier per country -> multiplier on hotel/activity prices.
COUNTRY_TIER = {
    "Japan": 1.05, "France": 1.05, "United Kingdom": 1.15, "United States": 1.2,
    "Italy": 1.0, "Spain": 0.9, "Singapore": 1.1, "Thailand": 0.55,
    "Australia": 1.1, "UAE": 1.15, "India": 0.5,
}

ACTIVITY_TEMPLATES = [
    ("Guided city walking tour", "sightseeing", (15, 60), "3 hours"),
    ("Street food tasting tour", "food", (25, 90), "3 hours"),
    ("Museum and gallery pass", "culture", (12, 45), "4 hours"),
    ("Historic landmark entry", "sightseeing", (8, 40), "2 hours"),
    ("Cooking class with local chef", "food", (40, 130), "4 hours"),
    ("Sunset viewpoint experience", "leisure", (10, 55), "2 hours"),
    ("Day trip to nearby town", "adventure", (55, 180), "8 hours"),
    ("Traditional cultural performance", "culture", (20, 95), "2 hours"),
    ("Local market and craft workshop", "culture", (18, 70), "3 hours"),
    ("River or harbour cruise", "leisure", (22, 85), "2 hours"),
    ("Cycling tour of the old town", "adventure", (25, 75), "3 hours"),
    ("Temple and shrine circuit", "culture", (10, 50), "4 hours"),
]


def _money(low: float, high: float, tier: float, rng: random.Random) -> float:
    return round(rng.uniform(low, high) * tier, 2)


# ---------------- knowledge documents ----------------
def write_knowledge(rng: random.Random) -> int:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    for old in KNOWLEDGE_DIR.glob("*.md"):
        old.unlink()

    record_count = 0
    for city, info in DESTINATIONS.items():
        country = info["country"]
        lines = [
            f"# {city}, {country} — Destination Guide (Demo)",
            "",
            DEMO_BANNER,
            "",
            f"**Destination:** {city}  ",
            f"**Country:** {country}  ",
            f"**Themes:** {', '.join(info['themes'])}",
            "",
        ]
        # One section per knowledge category — each becomes >= 1 vector record.
        for category in ("attractions", "food", "culture", "transportation",
                         "safety", "accommodation", "activities", "weather",
                         "local_customs"):
            text = info.get(category)
            if not text:
                continue
            title = category.replace("_", " ").title()
            lines += [
                f"## {title}",
                "",
                text,
                "",
            ]
            record_count += 1

        # Practical planning notes give the planner budget-shaped context.
        tier = COUNTRY_TIER.get(country, 1.0)
        daily_food = round(35 * tier)
        daily_local = round(12 * tier)
        lines += [
            "## Budget Planning Notes",
            "",
            f"Typical demo estimates for {city}: mid-range hotels around "
            f"${round(140 * tier)} per night, daily food budget about "
            f"${daily_food} per person, and local transport roughly "
            f"${daily_local} per person per day. Paid attractions average "
            f"${round(25 * tier)} per entry. These are planning estimates only, "
            "not live prices.",
            "",
            "## Suggested Pace",
            "",
            f"A relaxed pace in {city} means two main sights per day plus one "
            "meal experience. A packed pace can fit four sights but increases "
            "travel fatigue. Group activities by neighbourhood to reduce transit "
            "time.",
            "",
        ]
        record_count += 2

        slug = city.lower().replace(" ", "_")
        (KNOWLEDGE_DIR / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")

    return record_count


# ---------------- operational CSVs ----------------
def _write_csv(path, table: str, rows: list[dict]) -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS[table])
        writer.writeheader()
        writer.writerows(rows)


# Origins guaranteed to have a flight into every destination, so common demo
# queries ("from New York to Tokyo") always return results.
CORE_ORIGINS = ["New York", "London", "Delhi", "Singapore", "Dubai"]

FLIGHTS_PER_DESTINATION = 10
HOTELS_PER_DESTINATION = 8
ACTIVITIES_PER_DESTINATION = 8


def gen_flights(rng: random.Random) -> list[dict]:
    rows = []
    base = date(2026, 10, 1)
    n = 0
    for city, info in DESTINATIONS.items():
        tier = COUNTRY_TIER.get(info["country"], 1.0)
        # Guarantee the core origins, then fill with other hubs for variety.
        origins = [o for o in CORE_ORIGINS if o != city]
        others = [o for o in ORIGIN_HUBS if o != city and o not in origins]
        rng.shuffle(others)
        origins += others[:max(0, FLIGHTS_PER_DESTINATION - len(origins))]

        for i, origin in enumerate(origins):
            dep = base + timedelta(days=rng.randint(0, 27))
            ret = dep + timedelta(days=rng.choice([5, 6, 7, 8, 10, 12, 14]))
            # Keep most seats in economy so budget itineraries are feasible.
            cabin = "economy" if i < len(origins) - 2 else rng.choice(
                ["premium_economy", "business"]
            )
            mult = {"economy": 1.0, "premium_economy": 1.8, "business": 3.2}[cabin]
            n += 1
            rows.append({
                "flight_id": f"FL{n:04d}",
                "airline": rng.choice(AIRLINES),
                "origin": origin,
                "destination": city,
                "departure_date": dep.isoformat(),
                "return_date": ret.isoformat(),
                "price": round(rng.uniform(320, 980) * tier * mult, 2),
                "available_seats": rng.randint(2, 60),
                "class": cabin,
            })
    return rows


def gen_hotels(rng: random.Random) -> list[dict]:
    """8 hotels per destination with a guaranteed usable spread.

    Every destination gets at least one well-rated mid-range room at or below
    150 USD/night, so realistic demo queries ("mid-range hotel in Tokyo under
    $150") always return something even in expensive cities.
    """
    rows = []
    n = 0
    for city, info in DESTINATIONS.items():
        tier = COUNTRY_TIER.get(info["country"], 1.0)
        # 3 budget, 3 mid-range, 2 luxury.
        plan = ["budget"] * 3 + ["mid-range"] * 3 + ["luxury"] * 2
        names = rng.sample(HOTEL_NAME_PARTS["budget"], 3) \
            + rng.sample(HOTEL_NAME_PARTS["mid-range"], 3) \
            + rng.sample(HOTEL_NAME_PARTS["luxury"], 2)

        midrange_seen = 0
        for category, name_part in zip(plan, names):
            low, high = PRICE_BANDS[category]
            price = _money(low, high, tier, rng)
            rating = {
                "budget": round(rng.uniform(3.0, 4.1), 1),
                "mid-range": round(rng.uniform(3.8, 4.6), 1),
                "luxury": round(rng.uniform(4.4, 5.0), 1),
            }[category]

            if category == "mid-range":
                midrange_seen += 1
                # Force the first mid-range option into the popular
                # "good value, well rated" bracket regardless of city tier.
                if midrange_seen == 1:
                    price = round(rng.uniform(105, 148), 2)
                    rating = round(rng.uniform(4.0, 4.5), 1)

            n += 1
            rows.append({
                "hotel_id": f"HT{n:04d}",
                "hotel_name": f"{city} {name_part}",
                "destination": city,
                "rating": rating,
                "price_per_night": price,
                "available_rooms": rng.randint(1, 25),
                "category": category,
            })
    return rows


def gen_activities(rng: random.Random) -> list[dict]:
    """8 activities per destination, spread across categories.

    Enough variety that a 7-day itinerary can propose different things each day
    without repeating, and every destination has at least one food, one culture,
    and one sightseeing option.
    """
    rows = []
    n = 0
    for city, info in DESTINATIONS.items():
        tier = COUNTRY_TIER.get(info["country"], 1.0)

        # Guarantee one of each core category, then fill randomly.
        by_category: dict[str, list] = {}
        for template in ACTIVITY_TEMPLATES:
            by_category.setdefault(template[1], []).append(template)
        picks = [rng.choice(by_category[c]) for c in ("food", "culture", "sightseeing")
                 if c in by_category]
        remaining = [t for t in ACTIVITY_TEMPLATES if t not in picks]
        rng.shuffle(remaining)
        picks += remaining[:max(0, ACTIVITIES_PER_DESTINATION - len(picks))]

        for name, category, (low, high), duration in picks:
            n += 1
            rows.append({
                "activity_id": f"AC{n:04d}",
                "destination": city,
                "activity_name": f"{name} in {city}",
                "category": category,
                "price": _money(low, high, tier, rng),
                "duration": duration,
                "rating": round(rng.uniform(3.9, 5.0), 1),
            })
    return rows


def gen_bookings(rng: random.Random, hotels: list[dict], flights: list[dict],
                 activities: list[dict]) -> list[dict]:
    rows = []
    today = date(2026, 7, 25)
    for i in range(1, 61):
        kind = rng.choices(["hotel", "flight", "activity"], weights=[5, 4, 3])[0]
        if kind == "hotel":
            item = rng.choice(hotels)
            item_id = item["hotel_id"]
            nights = rng.randint(2, 9)
            cost = round(item["price_per_night"] * nights, 2)
        elif kind == "flight":
            item = rng.choice(flights)
            item_id = item["flight_id"]
            cost = round(item["price"] * rng.randint(1, 3), 2)
        else:
            item = rng.choice(activities)
            item_id = item["activity_id"]
            cost = round(item["price"] * rng.randint(1, 4), 2)

        rows.append({
            "booking_id": f"BK-DEMO{i:03d}",
            "booking_type": kind,
            "item_id": item_id,
            "traveler_name": rng.choice(DEMO_TRAVELERS),
            "booking_date": (today - timedelta(days=rng.randint(0, 120))).isoformat(),
            "status": rng.choices(["confirmed", "cancelled", "completed"],
                                  weights=[6, 1, 3])[0],
            "total_cost": cost,
        })
    return rows


def main() -> None:
    rng = random.Random(SEED)

    print("Generating destination knowledge documents...")
    records = write_knowledge(rng)
    print(f"  {len(DESTINATIONS)} destination guides, {records} knowledge sections")

    print("Generating operational seed data...")
    flights = gen_flights(rng)
    hotels = gen_hotels(rng)
    activities = gen_activities(rng)
    bookings = gen_bookings(rng, hotels, flights, activities)

    _write_csv(FLIGHTS_CSV, "flights", flights)
    _write_csv(HOTELS_CSV, "hotels", hotels)
    _write_csv(ACTIVITIES_CSV, "activities", activities)
    _write_csv(BOOKINGS_CSV, "bookings", bookings)

    print(f"  flights:    {len(flights):>4}  -> {FLIGHTS_CSV.name}")
    print(f"  hotels:     {len(hotels):>4}  -> {HOTELS_CSV.name}")
    print(f"  activities: {len(activities):>4}  -> {ACTIVITIES_CSV.name}")
    print(f"  bookings:   {len(bookings):>4}  -> {BOOKINGS_CSV.name}")
    print("\nAll generated data is synthetic DEMO data.")
    print("Next: uv run python -m ingest.build_vectordb")


if __name__ == "__main__":
    main()
