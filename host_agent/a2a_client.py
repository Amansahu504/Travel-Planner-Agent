"""Direct A2A client helpers for the host.

`router.py` reaches the remote agents through ADK's `RemoteA2aAgent`, which is
the normal user path. These helpers exist for health checks and diagnostics —
verifying that each agent's card is reachable before the UI accepts traffic, and
letting tests talk to an agent without spinning up the whole ADK runner.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx

from common.config import settings
from common.logging_utils import get_logger, log_event

logger = get_logger("host.a2a")

CARD_PATH = "/.well-known/agent-card.json"

AGENTS = {
    "travel_intelligence_agent": settings.rag_agent_url,
    "travel_operations_agent": settings.workflow_agent_url,
}


async def fetch_agent_card(base_url: str, timeout: float = 10.0) -> dict | None:
    """Fetch a remote agent's card, or None when unreachable."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(base_url.rstrip("/") + CARD_PATH)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            log_event(logger, "agent_card_unreachable", url=base_url,
                      error=f"{type(exc).__name__}: {exc}")
            return None


async def health_check() -> dict[str, dict]:
    """Check every remote agent's card concurrently. Never raises."""
    async def one(name: str, url: str) -> tuple[str, dict]:
        card = await fetch_agent_card(url)
        if card is None:
            return name, {"online": False, "url": url}
        return name, {
            "online": True,
            "url": url,
            "name": card.get("name"),
            "version": card.get("version"),
            "skills": [s.get("id") for s in card.get("skills", [])],
        }

    pairs = await asyncio.gather(*(one(n, u) for n, u in AGENTS.items()))
    status = dict(pairs)
    log_event(logger, "agent_health_check",
              online=[n for n, s in status.items() if s["online"]],
              offline=[n for n, s in status.items() if not s["online"]])
    return status


async def send_message(base_url: str, text: str, timeout: float = 600.0) -> str:
    """Send a raw A2A `message/send` request and return the text response.

    Used by diagnostics and tests; the normal path is ADK's RemoteA2aAgent.
    """
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
        raise RuntimeError(f"A2A error: {data['error']}")

    result = data.get("result", {})
    chunks: list[str] = []
    for artifact in result.get("artifacts") or []:
        for part in artifact.get("parts") or []:
            if part.get("text"):
                chunks.append(part["text"])
    if not chunks:
        message = (result.get("status") or {}).get("message") or {}
        for part in message.get("parts") or []:
            if part.get("text"):
                chunks.append(part["text"])
    return "\n".join(chunks)
