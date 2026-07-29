"""Agno Workflow for Remote Agent 2 — Travel Operations & Policy.

Structure (spec section 11):
    Step 1  classify : LLM structured output -> one of 7 operation categories
    Step 2  route    : Router picks the branch
              - search / budget / booking / retrieve_booking / update_booking /
                cancel_booking  -> agent with MCP Server 2 tools
              - policy          -> agent with MCP Server 3 tools
    Step 3  compose  : assemble the final response with a category header

Both branches use real MCP clients over streamable HTTP.
"""
from __future__ import annotations

from agno.tools.mcp import MCPTools
from agno.workflow import Router, Step, StepInput, StepOutput, Workflow

from common.config import settings
from common.llm import agno_model  # noqa: F401  (import also primes GEMINI env)
from common.logging_utils import get_logger, log_event, new_request_id
from common.schemas import OpsClassification
from remote_agent_2.agents import operations_agent, policy_agent

logger = get_logger("agent2.workflow")

CLASSIFY_INSTRUCTIONS = """\
Classify the user's travel-operations request into exactly one category:

- "search": looking for flights, hotels, or activities.
- "budget": estimating, totalling, or optimising trip cost.
- "booking": creating a NEW booking ("book the hotel", "reserve it").
- "retrieve_booking": looking up an existing booking ("show my booking").
- "update_booking": changing an existing booking ("change my hotel booking",
  "move my dates", "correct the name").
- "cancel_booking": cancelling an existing booking.
- "policy": asking about rules or terms — visas, passports, insurance, baggage,
  cancellation terms, refunds, safety guidance, or modification fees.

Note the difference: asking what the cancellation POLICY says is "policy";
asking to actually cancel a booking is "cancel_booking".
"""

OPERATIONS_CATEGORIES = {
    "search", "budget", "booking", "retrieve_booking",
    "update_booking", "cancel_booking",
}

HEADERS = {
    "search": "Travel search results",
    "budget": "Budget estimate",
    "booking": "Booking (demo)",
    "retrieve_booking": "Your bookings (demo)",
    "update_booking": "Booking update (demo)",
    "cancel_booking": "Booking cancellation (demo)",
    "policy": "Travel policy",
}


# ---------------- Step 1: classify ----------------
async def classify_step(step_input: StepInput) -> StepOutput:
    from agno.agent import Agent

    query = step_input.get_input_as_string()
    agent = Agent(
        model=agno_model(),
        output_schema=OpsClassification,
        instructions=CLASSIFY_INSTRUCTIONS,
    )
    try:
        resp = await agent.arun(query)
    except Exception as exc:
        log_event(logger, "classification_failed", error=str(exc))
        return StepOutput(content="search")  # safest default: read-only search

    content = resp.content
    if isinstance(content, OpsClassification):
        category = content.category
    else:
        category = str(content).strip().strip('"').lower()
    if category not in OPERATIONS_CATEGORIES and category != "policy":
        log_event(logger, "classification_invalid", raw=category)
        category = "search"

    log_event(logger, "request_classified", category=category)
    return StepOutput(content=category)


# ---------------- Step 2 branches ----------------
async def operations_step(step_input: StepInput) -> StepOutput:
    """Handle search / budget / booking lifecycle via MCP Server 2."""
    query = step_input.get_input_as_string()
    category = (step_input.get_step_content("classify") or "search").strip().lower()

    try:
        async with MCPTools(url=settings.mcp2_url, transport="streamable-http") as tools:
            agent = operations_agent(tools)
            resp = await agent.arun(
                f"Request category: {category}\n\nUser request: {query}"
            )
        log_event(logger, "mcp_branch_complete", server="mcp2", category=category)
        return StepOutput(content=resp.content)
    except Exception as exc:
        log_event(logger, "mcp_branch_failed", server="mcp2", error=str(exc))
        return StepOutput(content=(
            "I could not reach the travel operations service, so I cannot look "
            "up inventory or bookings right now. Please try again shortly."
        ))


async def policy_step(step_input: StepInput) -> StepOutput:
    """Handle travel policy questions via MCP Server 3."""
    query = step_input.get_input_as_string()

    try:
        async with MCPTools(url=settings.mcp3_url, transport="streamable-http") as tools:
            agent = policy_agent(tools)
            resp = await agent.arun(query)
        log_event(logger, "mcp_branch_complete", server="mcp3", category="policy")
        return StepOutput(content=resp.content)
    except Exception as exc:
        log_event(logger, "mcp_branch_failed", server="mcp3", error=str(exc))
        return StepOutput(content=(
            "I could not reach the travel policy service, so I cannot quote the "
            "policy right now. Please try again shortly."
        ))


OPERATIONS_STEP = Step(name="operations", executor=operations_step)
POLICY_STEP = Step(name="policy", executor=policy_step)


def route_selector(step_input: StepInput) -> list[Step]:
    category = (step_input.get_step_content("classify") or "").strip().lower()
    if category == "policy":
        return [POLICY_STEP]
    return [OPERATIONS_STEP]


ROUTER = Router(
    name="route",
    description="Route to the travel-operations agent (MCP Server 2) or the "
                "travel-policy agent (MCP Server 3).",
    selector=route_selector,
    choices=[OPERATIONS_STEP, POLICY_STEP],
)


# ---------------- Step 3: compose ----------------
async def compose_step(step_input: StepInput) -> StepOutput:
    branch_output = step_input.previous_step_content or "No result was produced."
    category = (step_input.get_step_content("classify") or "").strip().lower()
    header = HEADERS.get(category, "Result")

    # Footers stay honest about the data being sample data, but name no internal
    # component — this text is shown to the end user verbatim.
    footer = ("\n\n_Sample travel data — prices and availability are estimates, "
              "not live results. Please confirm before booking._")
    if category == "policy":
        footer = ("\n\n_Illustrative sample policy, not official airline, hotel, "
                  "or government policy. Confirm the real terms with the provider._")
    elif category in {"booking", "update_booking", "cancel_booking"}:
        footer = ("\n\n_Practice booking only — nothing has been reserved and no "
                  "payment was taken._")

    return StepOutput(content=f"**{header}**\n\n{branch_output}{footer}")


def build_workflow() -> Workflow:
    return Workflow(
        name="Travel Operations & Policy Workflow",
        description="Classifies a travel-operations request and routes it to the "
                    "operations tools (MCP Server 2) or policy resources "
                    "(MCP Server 3).",
        steps=[
            Step(name="classify", executor=classify_step),
            ROUTER,
            Step(name="compose", executor=compose_step),
        ],
    )


_workflow = None


async def answer(query: str) -> str:
    """Public entrypoint used by the A2A executor."""
    global _workflow

    request_id = new_request_id()
    log_event(logger, "request_received", request_id=request_id, query=query)

    if not query or not query.strip():
        return "Please tell me what you would like to search, budget, or book."

    if _workflow is None:
        _workflow = build_workflow()

    try:
        resp = await _workflow.arun(input=query)
    except Exception as exc:
        log_event(logger, "request_failed", request_id=request_id, error=str(exc))
        return ("I could not complete that travel operation because of an "
                "internal error. Please try again shortly.")

    content = resp.content if hasattr(resp, "content") else str(resp)
    result = str(content) if content else ""
    if not result.strip():
        return ("I could not produce a result for that request. Try being more "
                "specific, for example: 'Find a mid-range hotel in Tokyo under "
                "$150 per night'.")

    log_event(logger, "request_complete", request_id=request_id, chars=len(result))
    return result
