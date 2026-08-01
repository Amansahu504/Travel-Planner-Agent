"""A2A agent card definition for Remote Agent 2 (Travel Operations)."""
from __future__ import annotations

from a2a.types import AgentSkill

from common.a2a_server import make_agent_card
from common.config import settings

SKILLS = [
    AgentSkill(
        id="flight_search",
        name="Flight Search",
        description="Searches the demo flight inventory by origin, destination, "
                    "dates, and price cap, returning cheapest-first results.",
        tags=["flights", "search", "airfare"],
        examples=[
            "Find flights from New York to Tokyo in October.",
            "What are the cheapest flights to Rome under $700?",
        ],
    ),
    AgentSkill(
        id="hotel_search",
        name="Hotel Search",
        description="Searches the demo hotel inventory by destination, nightly "
                    "price cap, minimum rating, and category (budget, mid-range, "
                    "luxury), with stay-total estimates.",
        tags=["hotels", "accommodation", "search"],
        examples=[
            "Find a mid-range hotel in Tokyo under $150 per night.",
            "Show me 4-star hotels in Barcelona.",
        ],
    ),
    AgentSkill(
        id="activity_search",
        name="Activity Search",
        description="Searches demo activity and tour inventory by destination, "
                    "category, and price.",
        tags=["activities", "tours", "experiences"],
        examples=[
            "What food tours are available in Bangkok?",
            "Show cultural activities in Kyoto under $50.",
        ],
    ),
    AgentSkill(
        id="budget_estimation",
        name="Budget Estimation & Optimisation",
        description="Totals trip cost components, compares against a target "
                    "budget, and returns ranked savings levers when the trip is "
                    "over budget.",
        tags=["budget", "cost", "optimisation"],
        examples=[
            "Estimate the total for $1,800 flights, $900 hotels, and $400 food "
            "against a $3,000 budget.",
            "My trip costs $3,450 but my budget is $3,000 — how do I cut it?",
        ],
    ),
    AgentSkill(
        id="booking_management",
        name="Booking Management (Mock)",
        description="Creates, retrieves, updates, and cancels MOCK bookings in the "
                    "demo database. No real reservations and no payments.",
        tags=["booking", "reservation", "mock", "demo"],
        examples=[
            "Book hotel HT0042 for Demo Traveler A at $890.",
            "Show me booking BK-DEMO001.",
            "Change my hotel booking.",
            "Cancel booking BK-DEMO001.",
        ],
    ),
    AgentSkill(
        id="travel_policy_lookup",
        name="Travel Policy Lookup",
        description="Reads the demo travel policy documents (visa, passport, "
                    "insurance, baggage, hotel/flight cancellation, refunds, "
                    "transportation, safety, booking modification) and answers "
                    "with the concrete rules, versions, and effective dates.",
        tags=["policy", "cancellation", "refund", "visa", "baggage"],
        examples=[
            "What is the hotel cancellation policy?",
            "What is the baggage allowance in economy?",
            "How long do refunds take?",
        ],
    ),
]

AGENT_CARD = make_agent_card(
    name="Travel Operations Agent",
    description=(
        "Agno workflow agent for travel operations. Classifies each request, then "
        "routes it to flight/hotel/activity search, budget estimation, and mock "
        "booking management via MCP Server 2, or to travel policy documents via "
        "MCP Server 3. All inventory and bookings are synthetic demo data."
    ),
    url=settings.workflow_agent_url,
    skills=SKILLS,
)
