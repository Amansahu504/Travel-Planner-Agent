"""LangGraph StateGraph for Remote Agent 1 — corrective, self-reflective planning.

Flow (spec section 7):

    START -> parse_query -> decide_retrieval
      |-- direct ------------------------------------> retrieve_policies
      |-- retrieve -> retrieve_travel_context -> check_relevance
                                                   |-- relevant --> retrieve_policies
                                                   |-- weak -----> web_search
                                                                     -> check_web_relevance
                                                                          |-- relevant --> retrieve_policies
                                                                          |-- weak -----> rewrite_query -> (loop, capped)
    retrieve_policies -> generate_itinerary -> validate_itinerary -> critic
      |-- pass ------------------------> finalize_response -> END
      |-- fail (under cap) -> revise_itinerary -> validate_itinerary -> critic (loop)
      |-- fail (at cap) ---------------> finalize_response -> END

Loop guards: `retries` caps query rewrites, `iteration_count` caps revisions,
and the compiled graph also carries a recursion limit.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from common.config import settings
from common.logging_utils import get_logger, log_event, new_request_id
from remote_agent_1.nodes import critic as critic_nodes
from remote_agent_1.nodes import itinerary as itinerary_nodes
from remote_agent_1.nodes import parse as parse_nodes
from remote_agent_1.nodes import retrieve as retrieve_nodes
from remote_agent_1.nodes import websearch as web_nodes
from remote_agent_1.state import TravelState

logger = get_logger("agent1.graph")

RELEVANCE_THRESHOLD = 0.55


# ---------------- conditional edges ----------------
def route_after_decision(state: TravelState) -> str:
    return "retrieve" if state.get("needs_retrieval", True) else "skip"


def route_after_relevance(state: TravelState) -> str:
    """Good context proceeds; weak context triggers the web fallback."""
    score = state.get("relevance_score", 0.0)
    if score >= RELEVANCE_THRESHOLD:
        return "sufficient"
    if state.get("retries", 0) >= settings.max_retrieval_retries:
        # Out of correction budget — proceed with what we have.
        return "sufficient"
    return "insufficient"


def route_after_web_relevance(state: TravelState) -> str:
    """Relevant web results proceed; otherwise rewrite and retry (capped)."""
    score = state.get("relevance_score", 0.0)
    if score >= RELEVANCE_THRESHOLD:
        return "sufficient"
    if state.get("retries", 0) >= settings.max_retrieval_retries:
        return "sufficient"  # best effort rather than an infinite loop
    return "rewrite"


def route_after_critic(state: TravelState) -> str:
    """Pass -> finalize. Fail -> revise, unless the revision cap is reached."""
    critique = state.get("critique", {})
    passed = (critique.get("relevant", True)
              and critique.get("budget_valid", True)
              and critique.get("feasible", True))
    if passed:
        return "finalize"
    if state.get("iteration_count", 0) >= settings.max_revisions:
        log_event(logger, "revision_cap_reached",
                  iterations=state.get("iteration_count", 0))
        return "finalize"
    return "revise"


# ---------------- graph assembly ----------------
def build_graph():
    graph = StateGraph(TravelState)

    graph.add_node("parse_query", parse_nodes.parse_query)
    graph.add_node("decide_retrieval", parse_nodes.decide_retrieval)
    graph.add_node("retrieve_travel_context", retrieve_nodes.retrieve_travel_context)
    graph.add_node("check_relevance", retrieve_nodes.check_relevance)
    graph.add_node("web_search", web_nodes.web_search)
    graph.add_node("check_web_relevance", web_nodes.check_web_relevance)
    graph.add_node("rewrite_query", web_nodes.rewrite_query)
    graph.add_node("retrieve_policies", retrieve_nodes.retrieve_policies)
    graph.add_node("generate_itinerary", itinerary_nodes.generate_itinerary)
    graph.add_node("validate_itinerary", itinerary_nodes.validate_itinerary)
    graph.add_node("critic", critic_nodes.critic)
    graph.add_node("revise_itinerary", critic_nodes.revise_itinerary)
    graph.add_node("finalize_response", critic_nodes.finalize_response)

    graph.add_edge(START, "parse_query")
    graph.add_edge("parse_query", "decide_retrieval")

    graph.add_conditional_edges("decide_retrieval", route_after_decision, {
        "retrieve": "retrieve_travel_context",
        "skip": "retrieve_policies",
    })

    graph.add_edge("retrieve_travel_context", "check_relevance")
    graph.add_conditional_edges("check_relevance", route_after_relevance, {
        "sufficient": "retrieve_policies",
        "insufficient": "web_search",
    })

    graph.add_edge("web_search", "check_web_relevance")
    graph.add_conditional_edges("check_web_relevance", route_after_web_relevance, {
        "sufficient": "retrieve_policies",
        "rewrite": "rewrite_query",
    })
    # Rewritten query loops back into retrieval (the corrective cycle).
    graph.add_edge("rewrite_query", "retrieve_travel_context")

    graph.add_edge("retrieve_policies", "generate_itinerary")
    graph.add_edge("generate_itinerary", "validate_itinerary")
    graph.add_edge("validate_itinerary", "critic")

    graph.add_conditional_edges("critic", route_after_critic, {
        "finalize": "finalize_response",
        "revise": "revise_itinerary",
    })
    # Revised plans are re-validated and re-criticised (the reflection cycle).
    graph.add_edge("revise_itinerary", "validate_itinerary")

    graph.add_edge("finalize_response", END)

    return graph.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def answer(query: str) -> str:
    """Public entrypoint used by the A2A executor."""
    request_id = new_request_id()
    log_event(logger, "request_received", request_id=request_id, query=query)

    if not query or not query.strip():
        return "Please describe the trip you would like help with."

    try:
        result = await get_graph().ainvoke(
            {
                "user_query": query,
                "original_query": query,
                "retries": 0,
                "iteration_count": 0,
                "trace": [],
            },
            config={"recursion_limit": 40},
        )
    except Exception as exc:
        log_event(logger, "request_failed", request_id=request_id, error=str(exc))
        return ("I could not complete the travel plan because of an internal "
                "error. Please try rephrasing your request, or try again shortly.")

    final = result.get("final_answer") or result.get("itinerary") or ""
    if not final.strip():
        return ("I could not produce a plan for that request. Try naming a "
                "destination and trip length, for example: 'Plan 5 days in Rome "
                "for 2 people under $2,000'.")

    trace_lines = result.get("trace", [])
    log_event(logger, "request_complete", request_id=request_id,
              chars=len(final), steps=len(trace_lines))

    # Append the high-level trace so the host/UI can display execution flow.
    # This is status only — never internal reasoning.
    if trace_lines:
        final += ("\n\n<!--TRACE-->\n"
                  + "\n".join(f"- {line}" for line in trace_lines))
    return final
