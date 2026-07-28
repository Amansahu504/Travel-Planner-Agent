"""MCP Server 1 — Travel Knowledge Server (streamable-http, port 8001).

Exposes semantic search over the destination-knowledge vector store so Remote
Agent 1 (LangGraph) can ground its itineraries in retrieved context.

Tools:
    search_travel_knowledge  - semantic search + metadata filtering
    list_destinations        - which destinations the knowledge base covers

Run: uv run python -m mcp_server_1.main
(Build the vector DB first: uv run python -m ingest.build_vectordb)
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from common.config import settings
from common.vectordb import CATEGORIES
from mcp_server_1 import retriever

mcp = FastMCP(
    "travel-knowledge",
    instructions=(
        "Semantic retrieval over demo destination guides covering attractions, "
        "food, culture, transportation, safety, accommodation, activities, "
        "weather, and local customs for 23 cities across 11 countries. "
        "All content is synthetic demo data for a demonstration project."
    ),
    host=settings.host,
    port=settings.mcp1_port,
)


@mcp.tool(annotations={"title": "Search Travel Knowledge", "readOnlyHint": True})
def search_travel_knowledge(
    query: str,
    top_k: int = 5,
    destination: Optional[str] = None,
    category: Optional[str] = None,
    allowed_sources: Optional[list[str]] = None,
    country: Optional[str] = None,
) -> dict:
    """Search the travel knowledge base for destination information.

    Use this to ground recommendations in retrieved knowledge instead of
    guessing. Returns text chunks with metadata and a relevance score.

    Args:
        query: Natural-language information need, e.g. "best cultural
            experiences in Kyoto" or "how to get around London".
        top_k: How many chunks to return (default 5).
        destination: Optional city filter, e.g. "Kyoto", "Paris", "Tokyo".
        category: Optional topic filter. One of: attractions, food, culture,
            transportation, safety, accommodation, activities, weather,
            local_customs, budget, planning.
        allowed_sources: Optional list of source document names to restrict to.
        country: Optional country filter, e.g. "Japan", "Italy".

    Returns:
        dict with `results` (each having text, destination, country, category,
        season, source, tags, score), `count`, and `filters_applied`.
    """
    return retriever.search(
        query=query, top_k=top_k, destination=destination,
        category=category, allowed_sources=allowed_sources, country=country,
    )


@mcp.tool(annotations={"title": "List Destinations", "readOnlyHint": True})
def list_destinations() -> dict:
    """List every destination covered by the travel knowledge base, with country.

    Call this when you need to check whether a requested destination has
    knowledge coverage before planning.
    """
    return retriever.list_destinations()


@mcp.tool(annotations={"title": "List Knowledge Categories", "readOnlyHint": True})
def list_categories() -> dict:
    """List the knowledge categories available for the `category` filter."""
    return {"categories": CATEGORIES + ["budget", "planning"]}


if __name__ == "__main__":
    print(f"Travel Knowledge MCP server on {settings.mcp1_url}")
    mcp.run(transport="streamable-http")
