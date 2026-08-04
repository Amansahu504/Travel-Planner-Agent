"""Host / Router agent (Google ADK) acting as the A2A client.

The two remote agents are reached as genuine A2A peers via `RemoteA2aAgent`,
each loaded from its published AgentCard. They are exposed to the host LlmAgent
as `AgentTool`s rather than `sub_agents` for one important reason: a single user
request often needs BOTH specialists (spec scenario 10 — "plan a trip, find
hotels, estimate cost, and explain cancellation policies"). Sub-agent transfer
hands control to exactly one agent and never returns; tools let the host call
one or both, then synthesise a single consolidated answer.

The host never calls MCP tools directly — that is the remote agents' job.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)
from google.adk.tools.agent_tool import AgentTool
from langchain_core.messages import HumanMessage, SystemMessage

from common.config import settings
from common.llm import adk_model
from common.logging_utils import get_logger, log_event
from common.schemas import RoutingDecision

logger = get_logger("host.router")

# ---- Remote Agent 1: travel intelligence (LangGraph) ----
travel_intelligence_agent = RemoteA2aAgent(
    name="travel_intelligence_agent",
    description=(
        "Researches destinations and builds day-by-day itineraries using "
        "retrieval-augmented generation over travel knowledge documents. Handles "
        "destination research, attractions, food, culture, local customs, "
        "weather, safety, itinerary planning, pacing, and budget-aware plan "
        "optimisation with self-review."
    ),
    agent_card=f"{settings.rag_agent_url}{AGENT_CARD_WELL_KNOWN_PATH}",
    timeout=600.0,
)

# ---- Remote Agent 2: travel operations (Agno) ----
travel_operations_agent = RemoteA2aAgent(
    name="travel_operations_agent",
    description=(
        "Searches demo flight, hotel, and activity inventory; calculates and "
        "optimises trip budgets; manages mock bookings (create, retrieve, "
        "update, cancel); and answers travel policy questions about visas, "
        "passports, insurance, baggage, cancellations, refunds, transportation, "
        "safety, and booking modifications."
    ),
    agent_card=f"{settings.workflow_agent_url}{AGENT_CARD_WELL_KNOWN_PATH}",
    timeout=600.0,
)

ROUTING_INSTRUCTION = """\
You are the host router for a multi-agent travel planning system. You have two
specialist agents available as tools. Your job is to route the request, then
present one clear consolidated answer.

Choose tools like this:

- `travel_intelligence_agent` — destination research and itinerary planning:
  what to see and do, food and culture, local customs, weather, safety, and
  day-by-day plans with pacing and budget-aware optimisation.

- `travel_operations_agent` — operational tasks: searching specific flights,
  hotels, or activities with prices; calculating a budget total; creating,
  looking up, changing, or cancelling a booking; and quoting travel policies
  (visa, passport, insurance, baggage, cancellation, refund, modification).

- BOTH, in the same turn, when the request spans planning and operations — for
  example "plan a 7-day trip to Japan, find hotels, estimate the cost, and
  explain the cancellation policy". Send each agent the part of the request it
  owns, then merge their outputs.

Rules:
- Never answer a specialist question from your own knowledge. Always delegate.
- Never invent prices, availability, itinerary details, or policy terms. Use
  only what the agents return.
- When you call both agents, produce ONE merged answer: lead with the itinerary,
  then the operational details (hotels, costs), then the policy notes. Do not
  paste two disconnected replies or repeat the same content twice.
- Preserve the agents' data caveats: demo data, estimated prices, mock bookings,
  and fictional policies must stay labelled as such in your final answer.
- Keep the agents' markdown structure and tables intact.
- Respond directly yourself only for greetings, or to ask one clarifying
  question when the request is too vague to route (for example no destination
  and no question).
- Never ask the user for passport numbers, card details, or other sensitive
  personal data, and never claim a real reservation or payment has been made.
"""

root_agent = LlmAgent(
    name="travel_host_router",
    model=adk_model(),
    description="Routes travel requests to the correct remote A2A agent(s) and "
                "consolidates their responses.",
    instruction=ROUTING_INSTRUCTION,
    tools=[
        AgentTool(agent=travel_intelligence_agent),
        AgentTool(agent=travel_operations_agent),
    ],
)


# ---- structured routing classification (observability) ----
CLASSIFY_SYSTEM = """\
Classify which capability a travel request needs.

targets:
- travel_research: destination facts, recommendations, culture, food, safety
- trip_planning: a day-by-day itinerary
- booking: create / retrieve / change / cancel a booking
- budget: cost estimation or budget optimisation only
- policy: travel policy or terms questions
- combined_travel_request: spans planning AND operations (hotels, costs,
  bookings, or policies) in one request

Set needs_research_agent when destination research or itinerary planning is
required. Set needs_operations_agent when inventory search, budget calculation,
bookings, or policy lookup is required. A combined request sets both true.
"""


async def classify_route(query: str) -> RoutingDecision | None:
    """Predict the routing target as structured output.

    Used for logging, tests, and the UI's routing preview. The authoritative
    routing decision is which AgentTools the host LlmAgent actually invokes —
    that is captured from the run events in `runner.py`, so this classifier is
    an observability aid rather than the control path.
    """
    from common.llm import langchain_llm

    llm = langchain_llm().with_structured_output(RoutingDecision)
    try:
        decision = await llm.ainvoke([
            SystemMessage(content=CLASSIFY_SYSTEM),
            HumanMessage(content=query),
        ])
    except Exception as exc:
        log_event(logger, "route_classification_failed", error=str(exc))
        return None

    if not isinstance(decision, RoutingDecision):
        return None
    log_event(logger, "route_classified", target=decision.target,
              research=decision.needs_research_agent,
              operations=decision.needs_operations_agent)
    return decision
