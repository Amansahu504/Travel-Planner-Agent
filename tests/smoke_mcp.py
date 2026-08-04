"""Standalone smoke test: exercise all three MCP servers over streamable-HTTP.

Verifies real MCP client<->server communication (tools + resources), not mocks.
MCP Server 1 needs a Gemini key (it embeds the query); servers 2 and 3 do not.

Usage (servers must be running):
    uv run python -m tests.smoke_mcp
"""
from __future__ import annotations

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from common.config import settings
from common.logging_utils import enable_utf8_stdout

enable_utf8_stdout()


def _text(result) -> str:
    """Extract text payload from an MCP tool result."""
    chunks = []
    for item in result.content:
        text = getattr(item, "text", None)
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _brief(payload: str, limit: int = 220) -> str:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload[:limit].replace("\n", " ")
    return json.dumps(data)[:limit]


async def check_server(label: str, url: str, calls: list[tuple[str, dict]],
                       read_resources: list[str] | None = None) -> bool:
    print(f"\n=== {label} — {url} ===")
    try:
        async with streamablehttp_client(url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                print(f"  tools ({len(names)}): {', '.join(names)}")

                if read_resources is not None:
                    res = await session.list_resources()
                    uris = [str(r.uri) for r in res.resources]
                    print(f"  resources ({len(uris)}): {', '.join(uris[:4])}"
                          f"{' ...' if len(uris) > 4 else ''}")
                    for uri in read_resources:
                        got = await session.read_resource(uri)
                        body = got.contents[0].text if got.contents else ""
                        print(f"  resource {uri}: {len(body)} chars"
                              f"  -> {'OK' if len(body) > 200 else 'TOO SHORT'}")

                for tool_name, args in calls:
                    result = await session.call_tool(tool_name, args)
                    payload = _text(result)
                    status = "ERROR" if '"error"' in payload else "ok"
                    print(f"  call {tool_name}({', '.join(f'{k}={v!r}' for k, v in args.items())})"
                          f" -> {status}: {_brief(payload)}")
        return True
    except Exception as exc:
        print(f"  ✗ FAILED: {type(exc).__name__}: {exc}")
        return False


async def main() -> None:
    results = []

    # --- MCP Server 2: operations (no LLM needed) ---
    results.append(await check_server(
        "MCP Server 2 — Travel Operations", settings.mcp2_url,
        calls=[
            ("search_hotels", {"destination": "Tokyo", "max_price_per_night": 150,
                               "minimum_rating": 4.0}),
            ("search_flights", {"destination": "Tokyo", "origin": "New York"}),
            ("search_activities", {"destination": "Kyoto", "category": "culture"}),
            ("calculate_trip_budget", {"flight_cost": 1800, "hotel_cost": 1100,
                                       "food_cost": 500, "activity_cost": 300,
                                       "transportation_cost": 200,
                                       "target_budget": 3000, "travelers": 2}),
            ("retrieve_booking", {"booking_id": "BK-DEMO001"}),
            ("create_booking", {"booking_type": "hotel", "item_id": "HT0001",
                                "traveler_name": "Smoke Test", "total_cost": 450}),
            # input validation
            ("create_booking", {"booking_type": "spaceship", "item_id": "X",
                                "traveler_name": "Y", "total_cost": 1}),
        ],
    ))

    # --- MCP Server 3: policies (no LLM needed) ---
    results.append(await check_server(
        "MCP Server 3 — Travel Policies", settings.mcp3_url,
        calls=[
            ("list_policies", {}),
            ("find_policy", {"question": "what is the hotel cancellation policy?"}),
            ("get_policy", {"topic": "hotel-cancellation"}),
            ("get_policy", {"topic": "nonsense"}),  # error path
        ],
        read_resources=["travel://policies/index", "travel://policies/visa"],
    ))

    # --- MCP Server 1: knowledge retrieval (needs Gemini key for embeddings) ---
    if settings.llm_configured:
        results.append(await check_server(
            "MCP Server 1 — Travel Knowledge", settings.mcp1_url,
            calls=[
                ("list_destinations", {}),
                ("search_travel_knowledge", {"query": "best cultural experiences in Kyoto",
                                             "destination": "Kyoto",
                                             "category": "culture", "top_k": 3}),
                ("search_travel_knowledge", {"query": "getting around the city",
                                             "top_k": 2}),
                ("search_travel_knowledge", {"query": ""}),  # validation path
            ],
        ))
    else:
        print("\n=== MCP Server 1 skipped (no GOOGLE_API_KEY) ===")

    print("\n" + "=" * 60)
    print("RESULT:", "ALL SERVERS OK" if all(results) else "SOME SERVERS FAILED")


if __name__ == "__main__":
    asyncio.run(main())
