"""Shared state for the LangGraph travel-intelligence workflow (Remote Agent 1)."""
from __future__ import annotations

from typing import Any, TypedDict


class TravelState(TypedDict, total=False):
    # ---- input ----
    user_query: str          # current (possibly rewritten) search query
    original_query: str      # the user's first query, never mutated

    # ---- parsed trip specification ----
    destination: str
    origin: str
    duration: int            # days
    travelers: int
    budget: float            # total USD, 0 when unknown
    start_date: str
    preferences: dict[str, Any]   # interests, pace, accommodation, ...
    intent: str              # research | planning | policy

    # ---- retrieval ----
    needs_retrieval: bool
    retrieved_context: list[dict]
    web_results: list[dict]
    sources: list[str]
    relevance_score: float
    web_used: bool
    rewritten_query: str
    retries: int

    # ---- policy context (MCP Server 3) ----
    policy_context: list[dict]

    # ---- planning + reflection ----
    itinerary: str                 # markdown day-by-day plan
    budget_estimate: dict          # component breakdown + total
    budget_status: str             # within_budget | over_budget | unknown
    critique: dict                 # structured CritiqueResult
    iteration_count: int           # revision attempts made
    warnings: list[str]
    assumptions: list[str]

    # ---- output ----
    final_answer: str
    trace: list[str]               # high-level execution trace for the UI
