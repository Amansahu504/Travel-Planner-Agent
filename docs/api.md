# API reference

Every endpoint in the system, with copy-pasteable examples.

---

## Endpoint map

| Service | Base URL (local) | Protocol |
| --- | --- | --- |
| Gradio UI | `http://127.0.0.1:7860` | HTTP (browser) |
| Remote Agent 1 | `http://127.0.0.1:9001` | A2A JSON-RPC 2.0 |
| Remote Agent 2 | `http://127.0.0.1:9002` | A2A JSON-RPC 2.0 |
| MCP Server 1 | `http://127.0.0.1:8001/mcp` | MCP streamable HTTP |
| MCP Server 2 | `http://127.0.0.1:8002/mcp` | MCP streamable HTTP |
| MCP Server 3 | `http://127.0.0.1:8003/mcp` | MCP streamable HTTP |

---

## A2A endpoints

### `GET /.well-known/agent-card.json`

Returns the agent's capability card. No auth in this demo.

```bash
curl -s http://127.0.0.1:9001/.well-known/agent-card.json
```

Response shape:

```json
{
  "name": "Travel Intelligence Agent",
  "description": "LangGraph-based travel research and itinerary planning agent…",
  "url": "http://127.0.0.1:9001",
  "version": "1.0.0",
  "capabilities": { "streaming": true },
  "defaultInputModes": ["text", "text/plain"],
  "defaultOutputModes": ["text", "text/plain"],
  "skills": [
    {
      "id": "itinerary_planning",
      "name": "Itinerary Planning",
      "description": "Builds day-by-day itineraries optimised for budget, pace…",
      "tags": ["itinerary", "planning", "trip", "schedule"],
      "examples": ["Plan a 7-day trip to Japan for 2 people with a budget of $3,000."]
    }
  ]
}
```

Exported copies for offline inspection live at `remote_agent_1/agent_card.json` and
`remote_agent_2/agent_card.json` (regenerate with
`uv run python -m scripts.export_agent_cards`).

### `POST /` — `message/send`

Send a request and receive a completed task.

```bash
curl -s http://127.0.0.1:9002/ -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Find a mid-range hotel in Tokyo under $150 per night."}],"messageId":"m1"}}}'
```

Response (abridged):

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "id": "task-…",
    "contextId": "ctx-…",
    "status": { "state": "completed" },
    "artifacts": [
      {
        "name": "response",
        "parts": [{ "kind": "text", "text": "**Travel search results**\n\n| ID | Hotel…" }]
      }
    ]
  }
}
```

Task states: `submitted` → `working` → `completed`, or `failed` with an explanatory
message. Errors never surface a stack trace.

### Remote Agent 1 skills

| Skill id | Use it for |
| --- | --- |
| `destination_research` | Attractions, food, culture, transport, safety, customs |
| `itinerary_planning` | Day-by-day plans with pacing and per-day costs |
| `travel_recommendation` | Activity / food / accommodation suggestions |
| `travel_policy_lookup` | Policy context attached to a plan |
| `travel_rag` | Grounded answers with relevance grading and web fallback |
| `self_reflective_planning` | Budget validation, critique, revision |

### Remote Agent 2 skills

| Skill id | Use it for |
| --- | --- |
| `flight_search` | Flights by origin, destination, dates, price |
| `hotel_search` | Hotels by destination, price, rating, category |
| `activity_search` | Activities by destination, category, price |
| `budget_estimation` | Totals, budget comparison, savings levers |
| `booking_management` | Create / retrieve / update / cancel (mock) |
| `travel_policy_lookup` | Direct policy questions |

---

## MCP Server 1 — Travel Knowledge (`:8001/mcp`)

### `search_travel_knowledge`

| Argument | Type | Default | Notes |
| --- | --- | --- | --- |
| `query` | string | required | Natural-language information need |
| `top_k` | int | 5 | Max chunks to return |
| `destination` | string | – | City filter, e.g. `Kyoto` |
| `category` | string | – | See categories below |
| `allowed_sources` | string[] | – | Restrict to named source documents |
| `country` | string | – | Country filter, e.g. `Japan` |

Categories: `attractions`, `food`, `culture`, `transportation`, `safety`,
`accommodation`, `activities`, `weather`, `local_customs`, `budget`, `planning`.

Response:

```json
{
  "query": "best cultural experiences in Kyoto",
  "filters_applied": { "destination": "Kyoto", "category": "culture" },
  "filter_strategy": "exact",
  "count": 1,
  "results": [
    {
      "text": "Kyoto, Japan — Culture\n\nThe best-preserved traditional culture…",
      "destination": "Kyoto",
      "country": "Japan",
      "category": "culture",
      "season": "all",
      "source": "Kyoto Destination Guide (Demo)",
      "language": "en",
      "tags": ["temples", "culture", "food", "gardens", "history"],
      "score": 0.7541
    }
  ],
  "data_source": "internal travel knowledge base (demo destination guides)"
}
```

**`filter_strategy`** reports how literally the filters were honoured:

| Value | Meaning |
| --- | --- |
| `exact` | Your filters matched directly |
| `destination_as_country` | `destination` was a country name; fanned out to its cities |
| `without_category` | Category dropped to find results |
| `country_without_category` | Both relaxed |
| `unfiltered` | Pure semantic search; check each result's destination |

Anything other than `exact` also adds a human-readable `note`.

### `list_destinations`

No arguments. Returns all 23 covered destinations with their countries.

### `list_categories`

No arguments. Returns the valid `category` filter values.

---

## MCP Server 2 — Travel Operations (`:8002/mcp`)

### `search_flights`

`origin`, `destination`, `departure_date` (ISO), `return_date` (ISO), `max_price`,
`limit` — all optional. Sorted cheapest-first; only rows with seats available.

```json
{
  "count": 1,
  "flights": [{
    "flight_id": "FL0005", "airline": "AeroLink", "origin": "New York",
    "destination": "Tokyo", "departure_date": "2026-10-18",
    "return_date": "2026-10-28", "price": 375.89,
    "available_seats": 11, "class": "economy"
  }],
  "cheapest_price": 375.89,
  "note": "Demo data from a synthetic database. Prices and availability are estimates…"
}
```

### `search_hotels`

`destination`, `check_in`, `check_out`, `max_price_per_night`, `minimum_rating` (0–5),
`category` (`budget` | `mid-range` | `luxury`), `limit`. Sorted by rating then price.
Supplying both dates adds `estimated_total_for_stay` per row and `nights` at the top
level.

### `search_activities`

`destination`, `category` (`sightseeing` | `food` | `culture` | `adventure` | `leisure`),
`max_price`, `limit`. Sorted by rating.

### `calculate_trip_budget`

`flight_cost`, `hotel_cost`, `food_cost`, `transportation_cost`, `activity_cost`,
`miscellaneous_cost`, `target_budget`, `travelers`.

```json
{
  "breakdown": { "flight_cost": 2000.0, "hotel_cost": 1450.0, "…": 0.0 },
  "total_estimated_cost": 3450.0,
  "travelers": 2,
  "per_person_cost": 1725.0,
  "target_budget": 3000.0,
  "difference": 450.0,
  "within_budget": false,
  "status": "over budget",
  "suggested_savings": [
    { "lever": "Lower hotel category", "detail": "Move from luxury/mid-range…",
      "potential_saving": 435.0, "closes_gap": false }
  ]
}
```

`suggested_savings` is ranked by estimated saving; `closes_gap` marks levers that alone
would close the shortfall.

### Booking tools

| Tool | Required | Optional |
| --- | --- | --- |
| `create_booking` | `booking_type` (`flight`\|`hotel`\|`activity`\|`package`), `item_id`, `traveler_name`, `total_cost` | – |
| `retrieve_booking` | one of `booking_id` / `traveler_name` | – |
| `update_booking` | `booking_id` | `item_id`, `traveler_name`, `status`, `total_cost` |
| `cancel_booking` | `booking_id` | – |

`status` ∈ `confirmed`, `cancelled`, `completed`, `pending`.

All four are **mock**: they read and write a demo SQLite database. No reservation is
created anywhere, no payment is processed, and `cancel_booking` performs a soft cancel so
records are never destroyed. These tools accept no card, passport, or identity data.

---

## MCP Server 3 — Travel Policies (`:8003/mcp`)

### Resources

| URI | Document |
| --- | --- |
| `travel://policies/index` | Index of all policies |
| `travel://policies/visa` | Visa Policy (Demo) |
| `travel://policies/passport` | Passport Requirements Policy (Demo) |
| `travel://policies/insurance` | Travel Insurance Policy (Demo) |
| `travel://policies/baggage` | Airline Baggage Policy (Demo) |
| `travel://policies/hotel-cancellation` | Hotel Cancellation Policy (Demo) |
| `travel://policies/flight-cancellation` | Flight Cancellation Policy (Demo) |
| `travel://policies/refund` | Refund Policy (Demo) |
| `travel://policies/transportation` | Ground Transportation Policy (Demo) |
| `travel://policies/safety` | Travel Safety Guidelines (Demo) |
| `travel://policies/booking-modification` | Booking Modification Policy (Demo) |

All `text/markdown`. Each document carries `policy_name`, `category`, `destination`,
`version`, `effective_date`, and `source` in a metadata table, plus a prominent notice
that it is fictional.

### Tools

| Tool | Arguments | Returns |
| --- | --- | --- |
| `list_policies` | – | All topics with metadata |
| `get_policy` | `topic` | Full markdown + metadata + disclaimer |
| `find_policy` | `question`, `limit` (3) | Ranked topic matches with `match_score` |

Unknown topics return `{"error": …, "valid_topics": [...]}` rather than raising.

---

## Calling MCP servers from Python

```python
import asyncio, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client("http://127.0.0.1:8002/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print([t.name for t in tools.tools])

            result = await session.call_tool(
                "search_hotels",
                {"destination": "Tokyo", "max_price_per_night": 150,
                 "minimum_rating": 4.0},
            )
            print(json.loads(result.content[0].text))

asyncio.run(main())
```

---

## Error conventions

MCP tools never raise across the protocol boundary. Failures come back as data:

```json
{ "error": "booking_type must be one of ['activity', 'flight', 'hotel', 'package']",
  "status": "error" }
```

```json
{ "query": "", "count": 0, "results": [],
  "error": "query must be a non-empty string" }
```

A2A failures arrive as a task in state `failed` with a readable message. Detailed
diagnostics stay in the server logs.
