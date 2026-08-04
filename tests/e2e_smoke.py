"""End-to-end smoke test through the Host Router.

Exercises the full documented path for each scenario:
    user -> Host Router (ADK) -> A2A -> Remote Agent -> MCP Server -> back

Requires everything running (`uv run python run_all.py --backend-only`) and a
Gemini key in .env.

Usage:
    uv run python -m tests.e2e_smoke                 # a representative subset
    uv run python -m tests.e2e_smoke --all           # all 10 spec scenarios
    uv run python -m tests.e2e_smoke --only 4 7      # specific scenarios
"""
from __future__ import annotations

import argparse
import asyncio
import time

from common.config import settings
from common.logging_utils import enable_utf8_stdout
from host_agent.a2a_client import health_check
from host_agent.runner import HostRunner

enable_utf8_stdout()

# (number, label, query, expected agent(s))
SCENARIOS: list[tuple[int, str, str, list[str]]] = [
    (1, "Full trip planning",
     "Plan a 7-day trip to Japan for 2 people with a budget of $3,000.",
     ["travel_intelligence_agent"]),
    (2, "Personalized planning",
     "Plan a 5-day trip to Paris. I love museums and food but don't like nightlife.",
     ["travel_intelligence_agent"]),
    (3, "Budget optimization",
     "Plan a trip to London for $2,000. If it exceeds my budget, optimize it.",
     ["travel_intelligence_agent"]),
    (4, "Hotel search",
     "Find a mid-range hotel in Tokyo under $150 per night.",
     ["travel_operations_agent"]),
    (5, "Activity search",
     "What are the best cultural activities in Kyoto?",
     ["travel_intelligence_agent", "travel_operations_agent"]),
    (6, "Policy question",
     "What is the hotel cancellation policy?",
     ["travel_operations_agent"]),
    (7, "Booking (mock)",
     "Book hotel HT0004 for Demo Traveler A at a total cost of $890.",
     ["travel_operations_agent"]),
    (8, "Booking retrieval",
     "Show me booking BK-DEMO001.",
     ["travel_operations_agent"]),
    (9, "Booking update",
     "Change booking BK-DEMO002 to status confirmed.",
     ["travel_operations_agent"]),
    (10, "Multi-agent combined request",
     "Plan a 7-day trip to Japan, find suitable hotels, estimate the total cost, "
     "and explain the relevant cancellation policies.",
     ["travel_intelligence_agent", "travel_operations_agent"]),
]

DEFAULT_SUBSET = [4, 6, 10]


async def run_scenario(number: int, label: str, query: str,
                       expected: list[str]) -> bool:
    print(f"\n{'=' * 74}")
    print(f"SCENARIO {number}: {label}")
    print(f"{'=' * 74}")
    print(f"Query: {query}\n")

    runner = HostRunner()
    started = time.time()
    result = await runner.ask(query)
    elapsed = time.time() - started

    if result.error:
        print(f"  ✗ ERROR: {result.error}")
        return False

    print("--- Execution trace ---")
    for step in result.trace:
        print("  " + step)

    print(f"\n--- Answer ({len(result.answer)} chars, {elapsed:.1f}s) ---")
    body = result.answer.strip()
    print("  " + body[:1400].replace("\n", "\n  "))
    if len(body) > 1400:
        print(f"  ... [{len(body) - 1400} more chars]")

    # A scenario passes when the host actually delegated to an expected agent
    # and produced a non-trivial answer.
    delegated = [agent for agent in result.agents_called if agent in expected]
    ok = bool(delegated) and len(body) > 120

    print(f"\n  agents invoked: {result.agents_called or 'NONE'}")
    print(f"  expected one of: {expected}")
    print(f"  verdict: {'PASS' if ok else 'FAIL'}")
    return ok


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Run all 10 scenarios.")
    parser.add_argument("--only", nargs="*", type=int, help="Run specific scenarios.")
    args = parser.parse_args()

    if not settings.llm_configured:
        raise SystemExit("GOOGLE_API_KEY is not set in .env.")

    print("Checking remote agents...")
    status = await health_check()
    for name, info in status.items():
        mark = "✓" if info["online"] else "✗"
        print(f"  {mark} {name}: {info.get('name') if info['online'] else 'OFFLINE'}"
              f"  ({info['url']})")
    if not all(info["online"] for info in status.values()):
        raise SystemExit("Remote agents are not reachable — start them first with "
                         "`uv run python run_all.py --backend-only`.")

    if args.all:
        selected = SCENARIOS
    elif args.only:
        selected = [s for s in SCENARIOS if s[0] in args.only]
    else:
        selected = [s for s in SCENARIOS if s[0] in DEFAULT_SUBSET]

    results: list[tuple[int, str, bool]] = []
    for number, label, query, expected in selected:
        try:
            ok = await run_scenario(number, label, query, expected)
        except Exception as exc:
            print(f"  ✗ EXCEPTION: {type(exc).__name__}: {exc}")
            ok = False
        results.append((number, label, ok))

    print(f"\n{'=' * 74}\nSUMMARY\n{'=' * 74}")
    for number, label, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  Scenario {number}: {label}")
    passed = sum(1 for _, _, ok in results if ok)
    print(f"\n{passed}/{len(results)} scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
