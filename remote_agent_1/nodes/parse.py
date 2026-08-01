"""Nodes: parse_query and decide_retrieval."""
from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from common.logging_utils import get_logger, log_event
from common.schemas import TripSpec
from remote_agent_1.nodes.common import structured, trace
from remote_agent_1.state import TravelState

logger = get_logger("agent1.parse")

PARSE_SYSTEM = """\
You extract structured trip details from a traveller's request.

Rules:
- Only fill a field if the request states or clearly implies it. Never invent a
  destination, budget, or date.
- duration_days: if the user says "a week" use 7; "long weekend" use 3.
- budget: total for the whole trip in USD. If the user gives a per-person
  budget, multiply by the number of travellers.
- interests: short lowercase tags such as food, temples, anime, museums,
  nightlife, beaches, hiking, shopping, art, history.
- pace: "relaxed" if they dislike hectic schedules, "packed" if they want to
  maximise sights, otherwise "moderate".
- accommodation_pref: budget, mid-range, or luxury when indicated.
- wants_itinerary: false if the user only asks a factual question (for example
  "what are the best activities in Kyoto?") rather than asking for a plan.
"""


class RetrievalDecision(BaseModel):
    needs_retrieval: Literal["retrieve", "direct"] = Field(
        description="'retrieve' when destination knowledge would improve the "
                    "answer; 'direct' for greetings or generic questions that "
                    "need no destination facts."
    )
    intent: Literal["research", "planning", "policy"] = Field(
        description="'planning' for itinerary requests, 'research' for "
                    "destination questions, 'policy' for travel-policy questions."
    )


async def parse_query(state: TravelState) -> TravelState:
    """Extract destination, duration, travellers, budget, and preferences."""
    query = state.get("original_query", state.get("user_query", ""))

    spec = await structured(TripSpec, [
        SystemMessage(content=PARSE_SYSTEM),
        HumanMessage(content=query),
    ])

    if spec is None:  # structured output failed -> continue with empty spec
        log_event(logger, "parse_failed", query=query)
        return {
            "destination": "", "duration": 0, "travelers": 1, "budget": 0.0,
            "preferences": {}, "warnings": ["Could not parse trip details "
                                            "reliably; proceeding with defaults."],
            "trace": trace(state, "Parsed query (fallback: details unclear)"),
        }

    preferences = {
        "interests": spec.interests,
        "pace": spec.pace or "moderate",
        "accommodation": spec.accommodation_pref or "mid-range",
        "wants_itinerary": spec.wants_itinerary,
    }

    assumptions: list[str] = []
    duration = spec.duration_days
    travelers = max(1, spec.travelers)
    if spec.wants_itinerary and duration == 0:
        duration = 5
        assumptions.append("Trip length was not specified; assumed 5 days.")
    if not spec.travelers:
        assumptions.append("Number of travellers was not specified; assumed 1.")
    if not spec.pace:
        assumptions.append("Travel pace was not specified; assumed a moderate pace.")
    if not spec.accommodation_pref:
        assumptions.append("Accommodation preference was not stated; assumed mid-range.")

    log_event(logger, "query_parsed", destination=spec.destination or "-",
              duration=duration, travelers=travelers, budget=spec.budget,
              interests=spec.interests)

    return {
        "destination": spec.destination,
        "origin": spec.origin,
        "duration": duration,
        "travelers": travelers,
        "budget": spec.budget,
        "start_date": spec.start_date,
        "preferences": preferences,
        "assumptions": assumptions,
        "trace": trace(state, f"Parsed request → destination="
                              f"{spec.destination or 'unspecified'}, "
                              f"{duration or '?'} days, {travelers} traveller(s)"),
    }


async def decide_retrieval(state: TravelState) -> TravelState:
    """Decide whether destination knowledge retrieval is needed."""
    query = state.get("original_query", "")

    decision = await structured(RetrievalDecision, [
        SystemMessage(content=(
            "You route requests for a travel assistant whose knowledge base "
            "covers destination guides (attractions, food, culture, transport, "
            "safety, accommodation, activities, weather, local customs) for 23 "
            "cities, plus travel policy documents. Decide whether retrieval is "
            "needed and classify the intent.")),
        HumanMessage(content=query),
    ])

    if decision is None:
        # Safer default: retrieve. Grounded answers beat guesses.
        log_event(logger, "retrieval_decision_fallback")
        return {"needs_retrieval": True, "intent": "research",
                "trace": trace(state, "Retrieval decision: retrieve (default)")}

    needs = decision.needs_retrieval == "retrieve"
    log_event(logger, "retrieval_decision", needs_retrieval=needs,
              intent=decision.intent)
    return {
        "needs_retrieval": needs,
        "intent": decision.intent,
        "trace": trace(state, f"Retrieval decision: "
                              f"{'retrieve knowledge' if needs else 'answer directly'} "
                              f"(intent={decision.intent})"),
    }
