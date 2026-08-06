"""Tests for Remote Agent 2's Agno workflow (classification + tool routing)."""
from __future__ import annotations

import pytest

from agno.workflow import StepInput, StepOutput

from common.schemas import OpsClassification
from remote_agent_2 import workflow as wf
from tests.conftest import requires_llm, requires_mcp2, requires_mcp3


# ---------------- workflow structure ----------------
def test_workflow_builds_with_three_steps():
    built = wf.build_workflow()
    assert len(built.steps) == 3


def test_router_offers_both_branches():
    assert {step.name for step in wf.ROUTER.choices} == {"operations", "policy"}


def test_every_category_has_a_header():
    for category in wf.OPERATIONS_CATEGORIES | {"policy"}:
        assert category in wf.HEADERS


def test_category_set_matches_schema():
    """The workflow's categories must match the structured-output schema."""
    from typing import get_args

    schema_categories = set(get_args(
        OpsClassification.model_fields["category"].annotation
    ))
    assert schema_categories == wf.OPERATIONS_CATEGORIES | {"policy"}


# ---------------- routing ----------------
def _step_outputs(**steps: str) -> dict[str, StepOutput]:
    """Agno's StepInput expects StepOutput objects, not bare strings."""
    return {name: StepOutput(content=content, step_name=name)
            for name, content in steps.items()}


def _input_with_category(category: str) -> StepInput:
    return StepInput(input="test", previous_step_outputs=_step_outputs(classify=category))


@pytest.mark.parametrize("category", sorted({
    "search", "budget", "booking", "retrieve_booking",
    "update_booking", "cancel_booking",
}))
def test_operational_categories_route_to_mcp2_agent(category):
    steps = wf.route_selector(_input_with_category(category))
    assert [s.name for s in steps] == ["operations"]


def test_policy_routes_to_mcp3_agent():
    steps = wf.route_selector(_input_with_category("policy"))
    assert [s.name for s in steps] == ["policy"]


def test_unknown_category_defaults_to_operations():
    steps = wf.route_selector(_input_with_category("banana"))
    assert [s.name for s in steps] == ["operations"]


def test_missing_category_defaults_to_operations():
    steps = wf.route_selector(StepInput(input="test", previous_step_outputs={}))
    assert [s.name for s in steps] == ["operations"]


# ---------------- compose step ----------------
@pytest.mark.parametrize("category", ["search", "budget", "booking", "policy",
                                      "retrieve_booking", "cancel_booking"])
@pytest.mark.asyncio
async def test_compose_footer_hides_internal_names(category):
    """Footers reach the user verbatim — they must not name internal components."""
    step_input = StepInput(
        input="q",
        previous_step_outputs=_step_outputs(classify=category, operations="x",
                                            policy="x"),
    )
    out = (await wf.compose_step(step_input)).content.lower()
    for term in ("mcp", "server 2", "server 3", "a2a", "agno", "langgraph"):
        assert term not in out, f"{term!r} leaked into the {category} footer"


@pytest.mark.parametrize("category", ["search", "booking", "policy"])
@pytest.mark.asyncio
async def test_compose_footer_keeps_honesty(category):
    """Removing jargon must not remove the sample-data disclosure."""
    step_input = StepInput(
        input="q",
        previous_step_outputs=_step_outputs(classify=category, operations="x",
                                            policy="x"),
    )
    out = (await wf.compose_step(step_input)).content.lower()
    assert "sample" in out or "estimate" in out or "nothing has been reserved" in out


@pytest.mark.asyncio
async def test_compose_labels_policy_source():
    step_input = StepInput(
        input="q",
        previous_step_outputs=_step_outputs(classify="policy",
                                            policy="Policy text here"),
    )
    out = await wf.compose_step(step_input)
    assert "Travel policy" in out.content
    assert "sample policy" in out.content.lower()
    assert "not official" in out.content.lower()


@pytest.mark.asyncio
async def test_compose_labels_booking_as_mock():
    step_input = StepInput(
        input="q",
        previous_step_outputs=_step_outputs(classify="booking",
                                            operations="Booked."),
    )
    out = await wf.compose_step(step_input)
    lowered = out.content.lower()
    assert "nothing has been reserved" in lowered
    assert "no payment" in lowered


@pytest.mark.asyncio
async def test_compose_labels_search_as_estimates():
    step_input = StepInput(
        input="q",
        previous_step_outputs=_step_outputs(classify="search",
                                            operations="Rows."),
    )
    out = await wf.compose_step(step_input)
    assert "estimates" in out.content.lower()


# ---------------- empty input ----------------
@pytest.mark.asyncio
async def test_blank_query_short_circuits():
    result = await wf.answer("")
    assert "search, budget, or book" in result.lower()


# ---------------- LLM classification ----------------
@requires_llm
@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected", [
    ("Find a mid-range hotel in Tokyo under $150 per night.", "search"),
    ("What is the hotel cancellation policy?", "policy"),
    ("Show me booking BK-DEMO001.", "retrieve_booking"),
    ("Cancel booking BK-DEMO001.", "cancel_booking"),
])
async def test_classifier_assigns_expected_category(query, expected):
    out = await wf.classify_step(StepInput(input=query))
    assert out.content == expected, f"{query!r} classified as {out.content}"


@requires_llm
@pytest.mark.asyncio
async def test_policy_question_and_cancel_action_are_distinguished():
    """Asking about the cancellation policy is not the same as cancelling."""
    asking = await wf.classify_step(
        StepInput(input="What does the cancellation policy say about refunds?"))
    doing = await wf.classify_step(
        StepInput(input="Please cancel my booking BK-DEMO005."))
    assert asking.content == "policy"
    assert doing.content == "cancel_booking"


# ---------------- live branch execution ----------------
@requires_llm
@requires_mcp2
@pytest.mark.asyncio
async def test_operations_branch_calls_mcp_tools():
    step_input = StepInput(
        input="Find a mid-range hotel in Tokyo under $150 per night.",
        previous_step_outputs=_step_outputs(classify="search"),
    )
    out = await wf.operations_step(step_input)
    assert "HT" in out.content, "expected hotel ids from the demo database"


@requires_llm
@requires_mcp3
@pytest.mark.asyncio
async def test_policy_branch_reads_policy_document():
    out = await wf.policy_step(StepInput(input="What is the hotel cancellation policy?"))
    lowered = out.content.lower()
    assert "cancellation" in lowered
    assert "demo" in lowered
