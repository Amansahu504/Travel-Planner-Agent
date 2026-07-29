"""Nodes: web_search, check_web_relevance, rewrite_query.

Web search is the fallback when internal MCP retrieval is insufficient. Results
are always tagged so downstream generation can label web-derived information
distinctly from retrieved knowledge (spec section 15).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from common.config import settings
from common.logging_utils import get_logger, log_event
from remote_agent_1.nodes.common import structured, text, trace
from remote_agent_1.nodes.retrieve import RelevanceGrade
from remote_agent_1.state import TravelState

logger = get_logger("agent1.web")


async def web_search(state: TravelState) -> TravelState:
    """Search the web via Tavily. Degrades to a no-op when no key is configured."""
    query = state.get("user_query") or state.get("original_query", "")
    destination = state.get("destination")
    search_query = f"{query} {destination} travel guide".strip() if destination else query

    if not settings.tavily_api_key or "your_" in settings.tavily_api_key:
        log_event(logger, "web_search_skipped", reason="no_api_key")
        warnings = list(state.get("warnings", []))
        warnings.append("Web search is not configured (no TAVILY_API_KEY), so "
                        "the answer relies only on the internal knowledge base.")
        return {"web_results": [], "web_used": True, "warnings": warnings,
                "trace": trace(state, "Web search: SKIPPED (no API key)")}

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        resp = client.search(search_query, max_results=4)
        results = [
            {
                "text": item.get("content", ""),
                "url": item.get("url", "web"),
                "title": item.get("title", ""),
                "origin": "web_search",
            }
            for item in resp.get("results", [])
            if item.get("content")
        ]
    except Exception as exc:
        log_event(logger, "web_search_failed", error=str(exc))
        warnings = list(state.get("warnings", []))
        warnings.append("Web search failed, so the answer relies only on the "
                        "internal knowledge base.")
        return {"web_results": [], "web_used": True, "warnings": warnings,
                "trace": trace(state, "Web search: FAILED")}

    sources = list(state.get("sources", [])) + [r["url"] for r in results]
    log_event(logger, "web_search_complete", count=len(results), query=search_query)
    return {
        "web_results": results,
        "web_used": True,
        "sources": sources,
        "trace": trace(state, f"Web search → {len(results)} result(s)"),
    }


async def check_web_relevance(state: TravelState) -> TravelState:
    """Grade the web results the same way internal context is graded."""
    results = state.get("web_results", [])
    if not results:
        return {"trace": trace(state, "Web relevance check: FAIL (no results)")}

    context = "\n\n".join(f"[{r.get('title')}] {r.get('text', '')}"
                          for r in results)[:6000]

    grade = await structured(RelevanceGrade, [
        SystemMessage(content=("Grade whether the CONTEXT is relevant enough to "
                               "answer the travel REQUEST.")),
        HumanMessage(content=f"REQUEST:\n{state.get('original_query', '')}\n\n"
                             f"CONTEXT:\n{context}"),
    ])

    if grade is None:
        return {"relevance_score": 0.6,
                "trace": trace(state, "Web relevance check: PASS (grader unavailable)")}

    score = max(0.0, min(1.0, float(grade.score)))
    if not grade.relevant:
        score = min(score, 0.4)
    log_event(logger, "web_relevance_graded", relevant=grade.relevant, score=score)
    return {
        "relevance_score": score,
        "trace": trace(state, f"Web relevance check: "
                              f"{'PASS' if grade.relevant else 'FAIL'} "
                              f"(score={score:.2f})"),
    }


async def rewrite_query(state: TravelState) -> TravelState:
    """Rewrite the search query to be more retrievable, then loop back."""
    original = state.get("original_query", state.get("user_query", ""))
    previous = state.get("user_query", original)

    rewritten = await text([
        SystemMessage(content=(
            "Rewrite the traveller's request into a clearer, more searchable "
            "query for a travel knowledge base. Keep the destination and the "
            "core information need, drop conversational filler, and prefer "
            "concrete nouns. Return ONLY the rewritten query, nothing else.")),
        HumanMessage(content=f"Original request: {original}\n"
                             f"Previous query that retrieved poor results: {previous}"),
    ], temperature=0.3)

    rewritten = (rewritten or "").strip().strip('"')
    if not rewritten or rewritten.startswith("(LLM call failed"):
        rewritten = original  # give up rewriting rather than corrupt the query

    retries = state.get("retries", 0) + 1
    log_event(logger, "query_rewritten", attempt=retries, new_query=rewritten)
    return {
        "user_query": rewritten,
        "rewritten_query": rewritten,
        "retries": retries,
        "trace": trace(state, f"Rewrote query (attempt {retries}): {rewritten[:70]}"),
    }
