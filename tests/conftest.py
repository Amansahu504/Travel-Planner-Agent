"""Shared pytest fixtures and skip markers.

Tests are split by what they need:
  * pure unit tests            — always run (no network, no LLM)
  * tests needing a live server — skipped unless the port is open
  * tests needing an LLM key    — skipped unless GOOGLE_API_KEY is configured
"""
from __future__ import annotations

import socket

import pytest

from common.config import settings


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


requires_llm = pytest.mark.skipif(
    not settings.llm_configured,
    reason="GOOGLE_API_KEY not configured in .env",
)

requires_mcp1 = pytest.mark.skipif(
    not port_open(settings.mcp1_port),
    reason=f"MCP Server 1 not running on :{settings.mcp1_port}",
)

requires_mcp2 = pytest.mark.skipif(
    not port_open(settings.mcp2_port),
    reason=f"MCP Server 2 not running on :{settings.mcp2_port}",
)

requires_mcp3 = pytest.mark.skipif(
    not port_open(settings.mcp3_port),
    reason=f"MCP Server 3 not running on :{settings.mcp3_port}",
)

requires_agent1 = pytest.mark.skipif(
    not port_open(settings.rag_agent_port),
    reason=f"Remote Agent 1 not running on :{settings.rag_agent_port}",
)

requires_agent2 = pytest.mark.skipif(
    not port_open(settings.workflow_agent_port),
    reason=f"Remote Agent 2 not running on :{settings.workflow_agent_port}",
)


@pytest.fixture(scope="session", autouse=True)
def ensure_db():
    """Make sure the SQLite demo database exists and is seeded."""
    from common.db import init_db

    return init_db()


@pytest.fixture
def sample_booking():
    """Create a throwaway demo booking and cancel it afterwards."""
    from common import db

    row = db.create_booking("hotel", "HT0001", "Pytest Traveler", 199.99)
    yield row
    db.cancel_booking(row["booking_id"])
