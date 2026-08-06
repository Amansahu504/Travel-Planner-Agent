"""Tests for Remote Agent 1's LangGraph workflow.

The conditional-edge functions are pure, so all routing behaviour — including
the loop caps that prevent infinite execution — is tested without any LLM call.
A single end-to-end graph run is included behind the LLM marker.
"""
from __future__ import annotations

import pytest

from common.config import settings
from common.vectordb import collection_exists
from remote_agent_1 import graph as g
from tests.conftest import requires_llm, requires_mcp1

requires_vectordb = pytest.mark.skipif(
    not collection_exists(), reason="vector DB not built")


# ---------------- graph structure ----------------
def test_graph_compiles():
    assert g.build_graph() is not None


def test_graph_has_every_spec_node():
    compiled = g.build_graph()
    nodes = set(compiled.get_graph().nodes)
    for node in ("parse_query", "decide_retrieval", "retrieve_travel_context",
                 "check_relevance", "web_search", "check_web_relevance",
                 "rewrite_query", "retrieve_policies", "generate_itinerary",
                 "validate_itinerary", "critic", "revise_itinerary",
                 "finalize_response"):
        assert node in nodes, f"missing node: {node}"


# ---------------- retrieval routing ----------------
def test_route_skips_retrieval_when_not_needed():
    assert g.route_after_decision({"needs_retrieval": False}) == "skip"


def test_route_retrieves_by_default():
    assert g.route_after_decision({}) == "retrieve"


# ---------------- relevance gate ----------------
def test_good_relevance_proceeds():
    state = {"relevance_score": 0.9, "retries": 0}
    assert g.route_after_relevance(state) == "sufficient"


def test_weak_relevance_triggers_web_search():
    state = {"relevance_score": 0.2, "retries": 0}
    assert g.route_after_relevance(state) == "insufficient"


def test_relevance_threshold_boundary():
    at_threshold = {"relevance_score": g.RELEVANCE_THRESHOLD, "retries": 0}
    assert g.route_after_relevance(at_threshold) == "sufficient"


def test_retry_cap_stops_web_fallback_loop():
    """Once the retry budget is spent, proceed instead of looping."""
    state = {"relevance_score": 0.1, "retries": settings.max_retrieval_retries}
    assert g.route_after_relevance(state) == "sufficient"


# ---------------- web relevance gate ----------------
def test_relevant_web_results_proceed():
    assert g.route_after_web_relevance({"relevance_score": 0.8, "retries": 0}) == "sufficient"


def test_weak_web_results_trigger_rewrite():
    assert g.route_after_web_relevance({"relevance_score": 0.1, "retries": 0}) == "rewrite"


def test_rewrite_loop_is_capped():
    state = {"relevance_score": 0.0, "retries": settings.max_retrieval_retries}
    assert g.route_after_web_relevance(state) == "sufficient"


# ---------------- critic gate ----------------
def _critique(**overrides) -> dict:
    base = {"relevant": True, "budget_valid": True, "feasible": True,
            "preference_match": 0.9, "issues": [], "recommendations": []}
    base.update(overrides)
    return base


def test_passing_critique_finalizes():
    state = {"critique": _critique(), "iteration_count": 0}
    assert g.route_after_critic(state) == "finalize"


@pytest.mark.parametrize("failing_field", ["relevant", "budget_valid", "feasible"])
def test_any_failed_check_triggers_revision(failing_field):
    state = {"critique": _critique(**{failing_field: False}), "iteration_count": 0}
    assert g.route_after_critic(state) == "revise"


def test_revision_cap_prevents_infinite_loop():
    state = {"critique": _critique(budget_valid=False),
             "iteration_count": settings.max_revisions}
    assert g.route_after_critic(state) == "finalize"


def test_revision_allowed_just_below_cap():
    state = {"critique": _critique(feasible=False),
             "iteration_count": settings.max_revisions - 1}
    assert g.route_after_critic(state) == "revise"


def test_missing_critique_is_treated_as_pass():
    """A failed critic must not deadlock the graph."""
    assert g.route_after_critic({"critique": {}, "iteration_count": 0}) == "finalize"


# ---------------- budget parsing helper ----------------
def test_parses_bolded_total_row():
    from remote_agent_1.nodes.itinerary import _parse_total_from_markdown

    markdown = ("| Component | Cost |\n| --- | --- |\n"
                "| Flights | $1,200 |\n| **Total** | **$2,450.50** |")
    assert _parse_total_from_markdown(markdown) == 2450.50


def test_returns_none_when_no_total_present():
    from remote_agent_1.nodes.itinerary import _parse_total_from_markdown

    assert _parse_total_from_markdown("no costs here") is None


# ---------------- empty input handling ----------------
@pytest.mark.asyncio
async def test_blank_query_short_circuits():
    result = await g.answer("   ")
    assert "describe the trip" in result.lower()


# ---------------- one real run ----------------
@requires_llm
@requires_mcp1
@requires_vectordb
@pytest.mark.asyncio
async def test_direct_answer_path_end_to_end():
    """A factual question should retrieve and answer without an itinerary."""
    answer = await g.answer("What are the best cultural activities in Kyoto?")
    assert len(answer) > 200
    lowered = answer.lower()
    assert "kyoto" in lowered
    # Direct answers skip the itinerary scaffold.
    assert "day-by-day itinerary" not in lowered
    # Provenance must be disclosed.
    assert "sources" in lowered
