"""A2A agent card + server definition for Remote Agent 1 (Travel Intelligence)."""
from __future__ import annotations

from a2a.types import AgentSkill

from common.a2a_server import make_agent_card
from common.config import settings

SKILLS = [
    AgentSkill(
        id="destination_research",
        name="Destination Research",
        description="Researches destinations using retrieval over travel knowledge "
                    "documents covering attractions, food, culture, transport, "
                    "safety, weather, and local customs.",
        tags=["destination", "research", "rag", "travel"],
        examples=[
            "What are the best cultural activities in Kyoto?",
            "Tell me about getting around London.",
            "What should I know about local customs in Dubai?",
        ],
    ),
    AgentSkill(
        id="itinerary_planning",
        name="Itinerary Planning",
        description="Builds day-by-day itineraries optimised for budget, pace, "
                    "geographic proximity, and traveller interests, with a "
                    "morning/afternoon/evening structure and per-day cost estimates.",
        tags=["itinerary", "planning", "trip", "schedule"],
        examples=[
            "Plan a 7-day trip to Japan for 2 people with a budget of $3,000.",
            "Plan a 5-day trip to Paris. I love museums and food but not nightlife.",
        ],
    ),
    AgentSkill(
        id="travel_recommendation",
        name="Travel Recommendation",
        description="Recommends activities, food, and accommodation styles matched "
                    "to stated interests and travel pace.",
        tags=["recommendation", "activities", "food"],
        examples=[
            "Recommend food experiences in Osaka for a vegetarian traveller.",
            "What relaxed activities suit a family trip to Singapore?",
        ],
    ),
    AgentSkill(
        id="travel_policy_lookup",
        name="Travel Policy Lookup",
        description="Retrieves relevant demo travel policy documents (visa, "
                    "passport, insurance, baggage, cancellation, refunds) and "
                    "explains them in context.",
        tags=["policy", "visa", "cancellation", "insurance"],
        examples=[
            "What passport validity do I need?",
            "Explain the hotel cancellation terms for my trip.",
        ],
    ),
    AgentSkill(
        id="travel_rag",
        name="Corrective Retrieval-Augmented Generation",
        description="Grounds every answer in retrieved context, grades retrieval "
                    "relevance, and falls back to web search with query rewriting "
                    "when internal knowledge is insufficient.",
        tags=["rag", "retrieval", "grounding", "web-search"],
        examples=["Find information about typhoon season risk in Tokyo in October."],
    ),
    AgentSkill(
        id="self_reflective_planning",
        name="Self-Reflective Planning",
        description="Validates the itinerary budget arithmetically, critiques the "
                    "plan against the request, and revises it (up to a capped "
                    "number of attempts) including budget optimisation.",
        tags=["critic", "self-reflection", "budget", "optimisation"],
        examples=["Plan a trip to London for $2,000 and optimise it if it exceeds "
                  "my budget."],
    ),
]

AGENT_CARD = make_agent_card(
    name="Travel Intelligence Agent",
    description=(
        "LangGraph-based travel research and itinerary planning agent. Uses "
        "corrective retrieval-augmented generation over destination knowledge "
        "(MCP Server 1) and travel policy resources (MCP Server 3), with web "
        "search fallback, arithmetic budget validation, and a self-reflective "
        "critic/revision loop."
    ),
    url=settings.rag_agent_url,
    skills=SKILLS,
)
