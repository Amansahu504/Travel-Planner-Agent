"""Nodes: generate_itinerary and validate_itinerary.

Generation is grounded strictly in retrieved context (plus web results when the
fallback ran). Validation is deterministic Python arithmetic over the LLM's own
cost lines — arithmetic is far more reliable in code than in a model.
"""
from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from common.config import settings
from common.logging_utils import get_logger, log_event
from remote_agent_1.nodes.common import structured, text, trace
from remote_agent_1.state import TravelState

logger = get_logger("agent1.itinerary")

ITINERARY_SYSTEM = """\
You are an expert travel planner. Build a practical, grounded itinerary.

GROUNDING RULES (critical):
- Base recommendations on the CONTEXT provided. The context is your source of
  truth for what a destination offers.
- Label anything drawn from web results as "(web)".
- Never state that a specific hotel or flight is currently available, and never
  quote a price as live. All costs are planning estimates.
- If the context is thin on a point, say so rather than inventing detail.

VOICE:
- You are writing for a traveller, not an engineer. Never mention internal
  system names, servers, tools, retrieval, databases, or the words "MCP",
  "agent", "context", or "API". Say "sample estimates" rather than describing
  where the data came from technically.

ITINERARY QUALITY RULES:
- Group each day's activities by neighbourhood or area. Never schedule
  geographically distant activities on the same day without noting the transit.
- Respect the requested pace: relaxed = 2 main activities per day,
  moderate = 3, packed = 4.
- Vary the activity types across days; do not repeat the same kind of outing.
- Put arrival-day and departure-day logistics on those days, keeping them light.
- Match the traveller's stated interests. If they dislike something, omit it.

OUTPUT FORMAT (markdown, exactly this structure):

## Destination Summary
2-3 sentences on the destination and why it suits this traveller.

## Trip Overview
- **Destination:** ...
- **Duration:** N days
- **Travellers:** N
- **Travel style:** ...

## Day-by-Day Itinerary

### Day 1 — <short theme>
- **Morning:** ...
- **Afternoon:** ...
- **Evening:** ...
- **Meals:** ...
- **Transportation:** ...
- **Estimated cost:** $X (for the whole party)

(repeat for every day)

## Estimated Budget
| Component | Estimated Cost (USD) |
| --- | --- |
| Flights | $X |
| Accommodation | $X |
| Food | $X |
| Local transportation | $X |
| Activities and entries | $X |
| Miscellaneous | $X |
| **Total** | **$X** |

## Accommodation Recommendations
What type and area to book, with an estimated nightly rate.

## Food Recommendations
Specific dishes and dining styles from the context.

## Transportation Suggestions
How to get around, including any passes worth buying.

## Assumptions
Bullet list of every assumption made.

## Warnings and Uncertainties
Bullet list, including that prices are estimates to verify before booking.

## Alternative Options
2-3 concrete alternatives (different pace, cheaper variant, or nearby add-on).
"""


class CostLines(BaseModel):
    """Structured extraction of the cost table so validation can be exact."""
    flights: float = Field(default=0.0, description="Total flight cost in USD.")
    accommodation: float = Field(default=0.0, description="Total lodging cost in USD.")
    food: float = Field(default=0.0, description="Total food cost in USD.")
    transportation: float = Field(default=0.0, description="Local transport total in USD.")
    activities: float = Field(default=0.0, description="Activities total in USD.")
    miscellaneous: float = Field(default=0.0, description="Miscellaneous total in USD.")


def _format_context(state: TravelState) -> str:
    blocks: list[str] = []

    for item in state.get("retrieved_context", [])[:14]:
        blocks.append(
            f"[KNOWLEDGE BASE | {item.get('destination', '?')} | "
            f"{item.get('category', '?')} | source: {item.get('source', '?')}]\n"
            f"{item.get('text', '')}"
        )

    for item in state.get("web_results", [])[:4]:
        blocks.append(
            f"[WEB RESULT | {item.get('title', '')} | {item.get('url', '')}]\n"
            f"{item.get('text', '')}"
        )

    for policy in state.get("policy_context", [])[:2]:
        blocks.append(
            f"[POLICY DOCUMENT | {policy.get('policy_name')} | "
            f"version {policy.get('version')} | {policy.get('source')}]\n"
            f"{policy.get('content', '')[:2000]}"
        )

    return "\n\n---\n\n".join(blocks) if blocks else "(no context retrieved)"


def _request_brief(state: TravelState) -> str:
    prefs = state.get("preferences", {})
    budget = state.get("budget") or 0
    lines = [
        f"Original request: {state.get('original_query', '')}",
        f"Destination: {state.get('destination') or 'not specified'}",
        f"Duration: {state.get('duration') or 'not specified'} days",
        f"Travellers: {state.get('travelers', 1)}",
        f"Total budget: {f'${budget:,.0f} USD' if budget else 'not specified'}",
        f"Interests: {', '.join(prefs.get('interests', [])) or 'not specified'}",
        f"Pace: {prefs.get('pace', 'moderate')}",
        f"Accommodation preference: {prefs.get('accommodation', 'mid-range')}",
    ]
    if state.get("origin"):
        lines.append(f"Origin: {state['origin']}")
    if state.get("start_date"):
        lines.append(f"Start date: {state['start_date']}")
    return "\n".join(lines)


async def generate_itinerary(state: TravelState) -> TravelState:
    """Produce the itinerary (or a grounded direct answer for simple questions)."""
    wants_itinerary = state.get("preferences", {}).get("wants_itinerary", True)
    context = _format_context(state)

    if not wants_itinerary:
        # Factual question: answer concisely from context, no itinerary scaffold.
        answer = await text([
            SystemMessage(content=(
                "You are a travel information assistant. Answer using ONLY the "
                "CONTEXT below. Label anything from a web result as '(web)'. If "
                "the context does not cover the question, say so plainly. Be "
                "concise and specific, and cite the destination guide or policy "
                "name you used.\n\nCONTEXT:\n" + context)),
            HumanMessage(content=state.get("original_query", "")),
        ])
        log_event(logger, "direct_answer_generated", chars=len(answer))
        return {
            "itinerary": answer,
            "trace": trace(state, "Generated grounded answer (no itinerary requested)"),
        }

    itinerary = await text([
        SystemMessage(content=ITINERARY_SYSTEM + "\n\nCONTEXT:\n" + context),
        HumanMessage(content=_request_brief(state)),
    ], temperature=0.4)

    log_event(logger, "itinerary_generated", chars=len(itinerary),
              destination=state.get("destination") or "-")
    return {
        "itinerary": itinerary,
        "trace": trace(state, f"Generated itinerary ({len(itinerary)} chars)"),
    }


def _parse_total_from_markdown(itinerary: str) -> float | None:
    """Best-effort scrape of the bolded Total row, used as a cross-check."""
    match = re.search(r"\|\s*\*\*Total\*\*\s*\|\s*\*\*\$?([\d,]+(?:\.\d+)?)\*\*",
                      itinerary)
    if not match:
        match = re.search(r"Total\D{0,20}\$([\d,]+(?:\.\d+)?)", itinerary)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


async def validate_itinerary(state: TravelState) -> TravelState:
    """Extract the cost lines and check the total against the stated budget.

    Arithmetic is done in Python, not by the model, so the budget verdict is
    always internally consistent.
    """
    itinerary = state.get("itinerary", "")
    budget = float(state.get("budget") or 0)

    if not state.get("preferences", {}).get("wants_itinerary", True):
        return {"budget_status": "unknown"}

    lines = await structured(CostLines, [
        SystemMessage(content=("Extract the numeric cost components from the "
                               "itinerary's Estimated Budget table. Return USD "
                               "numbers only, 0 where a component is absent. Do "
                               "not include the Total row itself.")),
        HumanMessage(content=itinerary[:8000]),
    ])

    if lines is None:
        scraped = _parse_total_from_markdown(itinerary)
        log_event(logger, "budget_extraction_failed", scraped_total=scraped or "-")
        status = "unknown"
        if scraped and budget:
            status = "within_budget" if scraped <= budget else "over_budget"
        return {
            "budget_estimate": {"total": scraped or 0.0, "components": {},
                                "extraction": "fallback"},
            "budget_status": status,
            "trace": trace(state, "Budget validation: could not parse cost table"),
        }

    components = {
        "flight_cost": round(lines.flights, 2),
        "hotel_cost": round(lines.accommodation, 2),
        "food_cost": round(lines.food, 2),
        "transportation_cost": round(lines.transportation, 2),
        "activity_cost": round(lines.activities, 2),
        "miscellaneous_cost": round(lines.miscellaneous, 2),
    }
    total = round(sum(components.values()), 2)

    estimate: dict = {
        "components": components,
        "total": total,
        "travelers": state.get("travelers", 1),
        "per_person": round(total / max(1, state.get("travelers", 1)), 2),
        "extraction": "structured",
    }

    if budget:
        difference = round(total - budget, 2)
        estimate.update({
            "target_budget": budget,
            "difference": difference,
            "within_budget": difference <= 0,
        })
        status = "within_budget" if difference <= 0 else "over_budget"
    else:
        status = "unknown"

    log_event(logger, "budget_validated", total=total, target=budget or "-",
              status=status)

    trace_msg = (f"Budget validation: total ${total:,.0f}"
                 + (f" vs budget ${budget:,.0f} → {status.replace('_', ' ')}"
                    if budget else " (no budget given)"))
    return {
        "budget_estimate": estimate,
        "budget_status": status,
        "trace": trace(state, trace_msg),
    }
