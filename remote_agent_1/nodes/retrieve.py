"""Nodes: retrieve_travel_context, check_relevance, and policy retrieval.

Retrieval goes through real MCP tool calls to MCP Server 1 (travel knowledge)
and MCP Server 3 (travel policies) over streamable HTTP.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from common.logging_utils import get_logger, log_event
from remote_agent_1 import mcp_client
from remote_agent_1.nodes.common import structured, trace
from remote_agent_1.state import TravelState

logger = get_logger("agent1.retrieve")

# Categories worth pulling when building a full itinerary.
PLANNING_CATEGORIES = ["attractions", "food", "culture", "transportation",
                       "accommodation", "activities"]


class RelevanceGrade(BaseModel):
    relevant: bool = Field(description="True if the context can answer the request.")
    score: float = Field(description="Confidence from 0.0 to 1.0 that the "
                                     "context is sufficient.")
    missing: str = Field(default="", description="What is missing, if anything.")


async def retrieve_travel_context(state: TravelState) -> TravelState:
    """Fetch destination knowledge from MCP Server 1.

    For itinerary requests we run one targeted search per planning category so
    the generator sees attractions, food, culture, transport, and accommodation
    context. For simple questions one broad search is enough.
    """
    query = state.get("user_query") or state.get("original_query", "")
    destination = state.get("destination") or None
    wants_itinerary = state.get("preferences", {}).get("wants_itinerary", True)
    intent = state.get("intent", "research")

    collected: list[dict] = []
    errors: list[str] = []

    if wants_itinerary and intent == "planning" and destination:
        for category in PLANNING_CATEGORIES:
            payload = await mcp_client.search_knowledge(
                query=f"{category} in {destination}", top_k=2,
                destination=destination, category=category,
            )
            if payload.get("error"):
                errors.append(payload["error"])
            collected.extend(payload.get("results", []))
        # Plus a free-text pass for anything the categories missed.
        payload = await mcp_client.search_knowledge(query=query, top_k=3,
                                                    destination=destination)
        if payload.get("error"):
            errors.append(payload["error"])
        collected.extend(payload.get("results", []))
    else:
        payload = await mcp_client.search_knowledge(
            query=query, top_k=5, destination=destination,
        )
        if payload.get("error"):
            errors.append(payload["error"])
        collected.extend(payload.get("results", []))

    # De-duplicate on text while keeping the highest-scoring copy.
    unique: dict[str, dict] = {}
    for item in collected:
        text_key = (item.get("text") or "")[:160]
        if not text_key:
            continue
        if text_key not in unique or (item.get("score") or 0) > (unique[text_key].get("score") or 0):
            unique[text_key] = item
    results = sorted(unique.values(), key=lambda r: r.get("score") or 0, reverse=True)

    sources = sorted({r.get("source") for r in results if r.get("source")})
    log_event(logger, "mcp_retrieval", server="mcp1", count=len(results),
              destination=destination or "-", errors=len(errors))

    warnings = list(state.get("warnings", []))
    if errors and not results:
        warnings.append("The travel knowledge base could not be reached; "
                        "falling back to web search.")

    return {
        "retrieved_context": results,
        "sources": sources,
        "warnings": warnings,
        "trace": trace(state, f"MCP Server 1 → retrieved {len(results)} "
                              f"knowledge chunk(s)"),
    }


async def check_relevance(state: TravelState) -> TravelState:
    """Grade whether retrieved context is sufficient (corrective RAG gate)."""
    docs = state.get("retrieved_context", [])
    if not docs:
        log_event(logger, "relevance_graded", relevant=False, reason="no_docs")
        return {"relevance_score": 0.0,
                "trace": trace(state, "Relevance check: FAIL (no context found)")}

    context = "\n\n".join(
        f"[{d.get('destination')} / {d.get('category')}] {d.get('text', '')}"
        for d in docs
    )[:6000]

    grade = await structured(RelevanceGrade, [
        SystemMessage(content=(
            "Grade whether the CONTEXT contains enough destination information "
            "to answer the REQUEST. Be pragmatic: for itinerary planning, "
            "context covering attractions, food, and transport for the right "
            "destination is sufficient even if it lacks fine detail.")),
        HumanMessage(content=f"REQUEST:\n{state.get('original_query', '')}\n\n"
                             f"CONTEXT:\n{context}"),
    ])

    if grade is None:
        # Assume usable when grading fails but we do have documents.
        log_event(logger, "relevance_graded", relevant=True, reason="grader_failed")
        return {"relevance_score": 0.6,
                "trace": trace(state, "Relevance check: PASS (grader unavailable)")}

    score = max(0.0, min(1.0, float(grade.score)))
    if not grade.relevant:
        score = min(score, 0.4)
    log_event(logger, "relevance_graded", relevant=grade.relevant, score=score,
              missing=grade.missing or "-")

    return {
        "relevance_score": score,
        "trace": trace(state, f"Relevance check: "
                              f"{'PASS' if grade.relevant else 'FAIL'} "
                              f"(score={score:.2f})"),
    }


async def retrieve_policies(state: TravelState) -> TravelState:
    """Fetch relevant travel policies from MCP Server 3 when they matter.

    Runs for explicit policy questions and for full trip plans (where
    cancellation terms are genuinely useful to the traveller).
    """
    query = state.get("original_query", "")
    intent = state.get("intent", "research")
    wants_itinerary = state.get("preferences", {}).get("wants_itinerary", True)

    # Cheap keyword pre-check so we don't call MCP 3 on every research query.
    policy_words = ("policy", "polic", "cancel", "refund", "visa", "passport",
                    "insurance", "baggage", "luggage", "modify", "change my")
    mentions_policy = any(word in query.lower() for word in policy_words)

    if intent != "policy" and not mentions_policy and not wants_itinerary:
        return {"policy_context": []}

    matches = await mcp_client.find_policy(query, limit=2)
    topics = [m.get("topic") for m in matches.get("matches", []) if m.get("topic")]

    # A trip plan always benefits from cancellation terms even if unasked.
    if wants_itinerary and intent == "planning" and not topics:
        topics = ["hotel-cancellation"]

    policies: list[dict] = []
    for topic in topics[:2]:
        payload = await mcp_client.get_policy(topic)
        if payload.get("error"):
            continue
        policies.append({
            "topic": topic,
            "policy_name": payload.get("policy_name"),
            "version": payload.get("version"),
            "effective_date": payload.get("effective_date"),
            "source": payload.get("source"),
            "content": (payload.get("content") or "")[:4000],
        })

    log_event(logger, "mcp_retrieval", server="mcp3", count=len(policies),
              topics=topics)
    if not policies:
        return {"policy_context": []}

    return {
        "policy_context": policies,
        "trace": trace(state, f"MCP Server 3 → fetched {len(policies)} "
                              f"policy document(s): {', '.join(topics[:2])}"),
    }
