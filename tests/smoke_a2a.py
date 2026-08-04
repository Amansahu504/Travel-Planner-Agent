"""Standalone smoke test: real A2A communication with both remote agents.

Fetches each AgentCard from /.well-known/agent-card.json, then sends a real
A2A message over JSON-RPC and prints the response. This exercises genuine A2A
client<->server communication, not a mock.

Usage (MCP servers + both remote agents must be running):
    uv run python -m tests.smoke_a2a
    uv run python -m tests.smoke_a2a --agent 2      # only agent 2
"""
from __future__ import annotations

import argparse
import asyncio
from uuid import uuid4

import httpx

from common.config import settings
from common.logging_utils import enable_utf8_stdout

enable_utf8_stdout()

CARD_PATH = "/.well-known/agent-card.json"


async def fetch_card(base_url: str) -> dict | None:
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(base_url.rstrip("/") + CARD_PATH)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            print(f"  ✗ could not fetch agent card: {type(exc).__name__}: {exc}")
            return None


async def send_message(base_url: str, text: str, timeout: float = 300.0) -> str:
    """Send an A2A message/send request and extract the text response."""
    payload = {
        "jsonrpc": "2.0",
        "id": uuid4().hex,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "messageId": uuid4().hex,
            }
        },
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(base_url.rstrip("/") + "/", json=payload)
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        return f"(A2A error: {data['error']})"

    result = data.get("result", {})
    chunks: list[str] = []

    # Completed tasks carry their output in artifacts.
    for artifact in result.get("artifacts") or []:
        for part in artifact.get("parts") or []:
            if part.get("text"):
                chunks.append(part["text"])
    # Fall back to the final status message.
    if not chunks:
        message = (result.get("status") or {}).get("message") or {}
        for part in message.get("parts") or []:
            if part.get("text"):
                chunks.append(part["text"])
    if not chunks and result.get("parts"):
        for part in result["parts"]:
            if part.get("text"):
                chunks.append(part["text"])

    state = (result.get("status") or {}).get("state", "unknown")
    body = "\n".join(chunks) or "(no text content)"
    return f"[task state: {state}]\n{body}"


async def check_agent(label: str, base_url: str, queries: list[str]) -> bool:
    print(f"\n{'=' * 70}\n{label} — {base_url}\n{'=' * 70}")

    card = await fetch_card(base_url)
    if card is None:
        return False
    skills = card.get("skills", [])
    print(f"  ✓ AgentCard: {card.get('name')} v{card.get('version')}")
    print(f"    description: {(card.get('description') or '')[:90]}...")
    print(f"    skills ({len(skills)}): {', '.join(s.get('id', '?') for s in skills)}")
    print(f"    streaming: {(card.get('capabilities') or {}).get('streaming')}")

    ok = True
    for query in queries:
        print(f"\n  --> {query}")
        try:
            answer = await send_message(base_url, query)
        except Exception as exc:
            print(f"  ✗ A2A call failed: {type(exc).__name__}: {exc}")
            ok = False
            continue
        # Strip the internal trace marker for readability.
        display = answer.split("<!--TRACE-->")[0].strip()
        print("  <-- " + display[:900].replace("\n", "\n      "))
        if len(display) > 900:
            print(f"      ... ({len(display)} chars total)")
        if "TRACE" in answer:
            trace = answer.split("<!--TRACE-->")[1].strip()
            print("      [execution trace]")
            for line in trace.splitlines():
                print("       " + line.strip())
    return ok


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["1", "2", "both"], default="both")
    args = parser.parse_args()

    results = []

    if args.agent in ("2", "both"):
        results.append(await check_agent(
            "Remote Agent 2 — Travel Operations (Agno)",
            settings.workflow_agent_url,
            [
                "Find a mid-range hotel in Tokyo under $150 per night.",
                "What is the hotel cancellation policy?",
                "Show me booking BK-DEMO001.",
            ],
        ))

    if args.agent in ("1", "both"):
        results.append(await check_agent(
            "Remote Agent 1 — Travel Intelligence (LangGraph)",
            settings.rag_agent_url,
            [
                "What are the best cultural activities in Kyoto?",
                "Plan a 3-day trip to Rome for 2 people with a budget of $1,500.",
            ],
        ))

    print("\n" + "=" * 70)
    print("RESULT:", "ALL AGENTS OK" if all(results) else "SOME AGENTS FAILED")


if __name__ == "__main__":
    asyncio.run(main())
