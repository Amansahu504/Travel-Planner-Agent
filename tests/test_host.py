"""Tests for the host router: configuration, routing, and orchestration."""
from __future__ import annotations

import pytest

from common.schemas import RoutingDecision
from host_agent import router
from host_agent.gradio_app import compose_request
from host_agent.runner import AGENT_LABELS, HostRunner, _strip_trace
from tests.conftest import (
    requires_agent1, requires_agent2, requires_llm, requires_mcp2,
)


# ---------------- host wiring (offline) ----------------
def test_host_exposes_both_remote_agents_as_tools():
    assert len(router.root_agent.tools) == 2


def test_host_has_no_direct_mcp_access():
    """The host must never call MCP tools itself — only delegate over A2A."""
    tool_names = {getattr(t, "name", str(t)) for t in router.root_agent.tools}
    for forbidden in ("search_travel_knowledge", "search_hotels", "get_policy"):
        assert forbidden not in tool_names


def test_remote_agents_point_at_well_known_card_path():
    # ADK stores the card location it was constructed with on _agent_card_source
    # (the resolved AgentCard itself is lazily fetched into _agent_card).
    for agent in (router.travel_intelligence_agent, router.travel_operations_agent):
        assert str(agent._agent_card_source).endswith("/.well-known/agent-card.json")


def test_agent_names_match_runner_labels():
    assert router.travel_intelligence_agent.name in AGENT_LABELS
    assert router.travel_operations_agent.name in AGENT_LABELS


def test_routing_instruction_forbids_answering_directly():
    instruction = router.ROUTING_INSTRUCTION.lower()
    assert "delegate" in instruction
    assert "both" in instruction  # multi-agent orchestration is described


# ---------------- trace extraction ----------------
def test_strip_trace_splits_answer_and_trace():
    text = "The plan.\n\n<!--TRACE-->\n- step one\n- step two"
    answer, trace = _strip_trace(text)
    assert answer == "The plan."
    assert trace == ["step one", "step two"]


def test_strip_trace_without_marker_returns_no_trace():
    answer, trace = _strip_trace("Just an answer.")
    assert answer == "Just an answer."
    assert trace == []


# ---------------- structured form composition ----------------
def test_compose_request_includes_every_field():
    message = compose_request(
        destination="Tokyo", origin="New York", start_date="2026-10-05",
        end_date="2026-10-12", travelers=2, budget=3000, currency="USD",
        interests=["food", "temples"], travel_style="relaxed",
        accommodation="mid-range", extra="No early mornings please.",
    )
    for fragment in ("Tokyo", "New York", "2026-10-05", "2026-10-12",
                     "2 travellers", "3,000 USD", "food, temples", "relaxed",
                     "mid-range", "No early mornings"):
        assert fragment in message


def test_compose_request_handles_singular_traveller():
    message = compose_request("Rome", "", "", "", 1, 0, "USD", [],
                              "no preference", "no preference", "")
    assert "1 traveller" in message
    assert "travellers" not in message


def test_compose_request_omits_no_preference_values():
    message = compose_request("Rome", "", "", "", 2, 0, "USD", [],
                              "no preference", "no preference", "")
    assert "no preference" not in message


def test_compose_request_survives_empty_form():
    message = compose_request("", "", "", "", 0, 0, "USD", [], "", "", "")
    assert message.strip()


# ---------------- UI surface stays product-facing ----------------
# The user-visible UI must not leak implementation details. Internal names stay
# in logs and in runner.HostResult, never on screen.
FORBIDDEN_IN_UI = [
    "langgraph", "agno", "google adk", " adk", "mcp server", "mcp_server",
    "a2a", "remote agent", "vector db", "chroma", "gemini", "rag",
    "travel_intelligence_agent", "travel_operations_agent",
]


def _ui_visible_text() -> str:
    """Every user-visible string literal the UI renders."""
    from host_agent import gradio_app as app

    parts = [
        app.HERO, app.GREETING, app.FOOTER,
        " ".join(label for label, _ in app.SUGGESTIONS),
        " ".join(request for _, request in app.SUGGESTIONS),
        " ".join(app.INTERESTS),
    ]
    return " ".join(parts).lower()


@pytest.mark.parametrize("term", FORBIDDEN_IN_UI)
def test_ui_text_hides_implementation_details(term):
    assert term not in _ui_visible_text(), (
        f"{term!r} leaks into the user-facing UI copy"
    )


def test_trace_panel_is_disabled():
    from host_agent import gradio_app as app

    assert app.SHOW_TRACE is False


def test_trace_is_still_captured_for_logging():
    """Turning the panel off must not remove the underlying capture."""
    from host_agent.runner import HostResult

    assert "trace" in HostResult.__dataclass_fields__
    assert "agents_called" in HostResult.__dataclass_fields__


def test_ui_keeps_the_demo_data_disclosure():
    """Honesty about synthetic data is not optional, even in a prettier UI."""
    from host_agent import gradio_app as app

    footer = app.FOOTER.lower()
    assert "sample" in footer or "demo" in footer
    assert "estimate" in footer
    assert "no payment" in footer or "nothing is reserved" in footer


def test_ui_builds_without_error():
    from host_agent.gradio_app import build_ui

    assert build_ui() is not None


# ---------------- structured routing classification ----------------
@requires_llm
@pytest.mark.asyncio
@pytest.mark.parametrize("query,expect_research,expect_operations", [
    ("Plan a 5-day trip to Paris.", True, False),
    ("Find a hotel in Tokyo under $150.", False, True),
    ("What is the refund policy?", False, True),
    ("Plan a 7-day trip to Japan, find hotels, estimate the cost, and explain "
     "the cancellation policies.", True, True),
])
async def test_route_classification(query, expect_research, expect_operations):
    decision = await router.classify_route(query)
    assert isinstance(decision, RoutingDecision)
    assert decision.needs_research_agent is expect_research
    assert decision.needs_operations_agent is expect_operations


@requires_llm
@pytest.mark.asyncio
async def test_combined_request_is_classified_as_combined():
    decision = await router.classify_route(
        "Plan a 7-day trip to Japan, find suitable hotels, estimate the total "
        "cost, and explain the relevant cancellation policies."
    )
    assert decision.target == "combined_travel_request"


# ---------------- live orchestration ----------------
@requires_agent2
@requires_mcp2
@requires_llm
@pytest.mark.asyncio
async def test_host_delegates_operational_request_to_agent_2():
    result = await HostRunner().ask("Find a mid-range hotel in Tokyo under $150 "
                                   "per night.")
    assert result.error is None
    assert "travel_operations_agent" in result.agents_called
    assert "HT" in result.answer
    assert result.trace


@requires_agent1
@requires_agent2
@requires_llm
@pytest.mark.asyncio
async def test_host_trace_records_a2a_delegation():
    result = await HostRunner().ask("What are the best cultural activities in Kyoto?")
    assert result.error is None
    assert result.agents_called
    assert any("A2A call" in step for step in result.trace)


@pytest.mark.asyncio
async def test_blank_query_short_circuits():
    result = await HostRunner().ask("   ")
    assert "enter a travel request" in result.answer.lower()
