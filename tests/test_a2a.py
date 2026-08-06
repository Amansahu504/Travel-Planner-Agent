"""Tests for A2A agent cards and real A2A client<->server communication."""
from __future__ import annotations

import pytest

from common.config import settings
from host_agent import a2a_client
from remote_agent_1.a2a_server import AGENT_CARD as CARD_1
from remote_agent_2.a2a_server import AGENT_CARD as CARD_2
from tests.conftest import (
    requires_agent1, requires_agent2, requires_llm, requires_mcp2,
)


# ---------------- card definitions (offline) ----------------
@pytest.mark.parametrize("card", [CARD_1, CARD_2])
def test_card_has_required_fields(card):
    assert card.name
    assert card.description
    assert card.url
    assert card.version
    assert card.skills
    assert card.capabilities.streaming is True
    assert "text" in card.default_input_modes
    assert "text" in card.default_output_modes


def test_agent_1_declares_expected_skills():
    ids = {skill.id for skill in CARD_1.skills}
    assert {"destination_research", "itinerary_planning", "travel_recommendation",
            "travel_policy_lookup", "travel_rag",
            "self_reflective_planning"} == ids


def test_agent_2_declares_expected_skills():
    ids = {skill.id for skill in CARD_2.skills}
    assert {"flight_search", "hotel_search", "activity_search",
            "budget_estimation", "booking_management",
            "travel_policy_lookup"} == ids


@pytest.mark.parametrize("card", [CARD_1, CARD_2])
def test_every_skill_has_description_and_examples(card):
    for skill in card.skills:
        assert skill.name
        assert skill.description
        assert skill.tags
        assert skill.examples, f"{skill.id} has no examples"


def test_cards_are_on_distinct_urls():
    assert CARD_1.url != CARD_2.url


def test_card_urls_match_configuration():
    assert CARD_1.url == settings.rag_agent_url
    assert CARD_2.url == settings.workflow_agent_url


# ---------------- exported json stays in sync ----------------
@pytest.mark.parametrize("module,card", [
    ("remote_agent_1", CARD_1),
    ("remote_agent_2", CARD_2),
])
def test_exported_agent_card_json_matches_live_card(module, card):
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / module / "agent_card.json"
    if not path.exists():
        pytest.skip(f"{path.name} not exported yet "
                    "(run: uv run python -m scripts.export_agent_cards)")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["name"] == card.name
    assert {s["id"] for s in saved["skills"]} == {s.id for s in card.skills}


# ---------------- live agent cards ----------------
@requires_agent1
@pytest.mark.asyncio
async def test_agent_1_card_is_served():
    card = await a2a_client.fetch_agent_card(settings.rag_agent_url)
    assert card is not None
    assert card["name"] == CARD_1.name
    assert len(card["skills"]) == len(CARD_1.skills)


@requires_agent2
@pytest.mark.asyncio
async def test_agent_2_card_is_served():
    card = await a2a_client.fetch_agent_card(settings.workflow_agent_url)
    assert card is not None
    assert card["name"] == CARD_2.name


@requires_agent1
@requires_agent2
@pytest.mark.asyncio
async def test_health_check_reports_both_agents_online():
    status = await a2a_client.health_check()
    assert set(status) == {"travel_intelligence_agent", "travel_operations_agent"}
    assert all(info["online"] for info in status.values())


@pytest.mark.asyncio
async def test_unreachable_agent_returns_none_not_exception():
    card = await a2a_client.fetch_agent_card("http://127.0.0.1:1", timeout=2.0)
    assert card is None


# ---------------- real A2A message exchange ----------------
@requires_agent2
@requires_mcp2
@requires_llm
@pytest.mark.asyncio
async def test_a2a_message_round_trip_to_agent_2():
    reply = await a2a_client.send_message(
        settings.workflow_agent_url,
        "Show me booking BK-DEMO001.",
    )
    assert reply.strip()
    assert "BK-DEMO001" in reply
