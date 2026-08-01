"""Typed models and structured-output schemas shared across the system.

These give us (a) validated LLM structured outputs and (b) a single definition
of the itinerary / budget shapes the agents pass around.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---- Host routing ----
RouteTarget = Literal[
    "travel_research",   # destination knowledge, recommendations  -> Remote Agent 1
    "trip_planning",     # full itinerary                          -> Remote Agent 1
    "booking",           # create/retrieve/update/cancel booking   -> Remote Agent 2
    "budget",            # cost estimation                         -> Remote Agent 2
    "policy",            # travel policies                         -> Remote Agent 2
    "combined_travel_request",  # needs both agents
]


class RoutingDecision(BaseModel):
    """Structured routing output for the host (used for logging/observability;
    the ADK router itself delegates via sub-agents)."""
    target: RouteTarget = Field(description="Which capability the query needs.")
    needs_research_agent: bool = Field(
        description="True if destination research / itinerary planning is required."
    )
    needs_operations_agent: bool = Field(
        description="True if hotels/flights/activities/budget/booking/policy is required."
    )
    reason: str = Field(description="One short sentence explaining the decision.")


# ---- Trip parsing (LangGraph parse_query node) ----
class TripSpec(BaseModel):
    destination: str = Field(default="", description="Primary destination city/country.")
    origin: str = Field(default="", description="Origin city if provided, else empty.")
    duration_days: int = Field(default=0, description="Trip length in days; 0 if unknown.")
    travelers: int = Field(default=1, description="Number of travelers; default 1.")
    budget: float = Field(default=0.0, description="Total budget in USD; 0 if unknown.")
    start_date: str = Field(default="", description="ISO start date if provided.")
    interests: list[str] = Field(default_factory=list, description="Themes: food, temples, anime, museums, nightlife, etc.")
    accommodation_pref: str = Field(default="", description="e.g. budget, mid-range, luxury.")
    pace: str = Field(default="", description="relaxed | moderate | packed, if implied.")
    wants_itinerary: bool = Field(default=True, description="Does the user want a day-by-day plan?")


# ---- Critic / self-reflection node ----
class CritiqueResult(BaseModel):
    relevant: bool = Field(description="Itinerary matches the user's request.")
    budget_valid: bool = Field(description="Estimated cost is within the stated budget (or no budget given).")
    feasible: bool = Field(description="Geographically/temporally realistic, not too hectic.")
    preference_match: float = Field(description="0..1 how well activities match stated interests.")
    issues: list[str] = Field(default_factory=list, description="Concrete problems found.")
    recommendations: list[str] = Field(default_factory=list, description="Concrete fixes.")


# ---- Operations classification (Agno workflow) ----
OpsCategory = Literal[
    "search",           # flights/hotels/activities lookup
    "budget",           # calculate trip budget
    "booking",          # create booking
    "retrieve_booking",
    "update_booking",
    "cancel_booking",
    "policy",           # travel policy lookup
]


class OpsClassification(BaseModel):
    category: OpsCategory = Field(description="Which travel-operations action the request needs.")


# ---- Budget breakdown (returned by MCP tool + used in UI) ----
class BudgetBreakdown(BaseModel):
    flight_cost: float = 0.0
    hotel_cost: float = 0.0
    food_cost: float = 0.0
    transportation_cost: float = 0.0
    activity_cost: float = 0.0
    miscellaneous_cost: float = 0.0

    @property
    def total(self) -> float:
        return round(
            self.flight_cost + self.hotel_cost + self.food_cost
            + self.transportation_cost + self.activity_cost + self.miscellaneous_cost,
            2,
        )
