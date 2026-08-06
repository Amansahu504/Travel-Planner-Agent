"""Tests for MCP Server 1 — travel knowledge retrieval.

Semantic search needs Gemini embeddings, so retrieval tests are marked
`requires_llm`. The filter-composition logic is pure and always runs.
"""
from __future__ import annotations

import json

import pytest

from common.config import settings
from common.vectordb import collection_exists
from mcp_server_1 import retriever
from tests.conftest import requires_llm, requires_mcp1

requires_vectordb = pytest.mark.skipif(
    not collection_exists(),
    reason="vector DB not built (run: uv run python -m ingest.build_vectordb)",
)


# ---------------- filter composition (pure) ----------------
def test_build_where_no_filters_is_none():
    assert retriever.build_where() is None


def test_build_where_single_filter_is_flat():
    assert retriever.build_where(destination="Kyoto") == {"destination": "Kyoto"}


def test_build_where_titlecases_destination():
    assert retriever.build_where(destination="new york") == {"destination": "New York"}


def test_build_where_lowercases_category():
    assert retriever.build_where(category="CULTURE") == {"category": "culture"}


def test_build_where_multiple_filters_use_and():
    where = retriever.build_where(destination="Kyoto", category="food")
    assert "$and" in where
    assert len(where["$and"]) == 2


def test_build_where_allowed_sources_uses_in():
    where = retriever.build_where(allowed_sources=["A", "B"])
    assert where == {"source": {"$in": ["A", "B"]}}


# ---------------- input validation ----------------
def test_empty_query_is_rejected():
    result = retriever.search("")
    assert result["count"] == 0
    assert "error" in result


def test_whitespace_query_is_rejected():
    assert "error" in retriever.search("   ")


# ---------------- semantic retrieval ----------------
@requires_llm
@requires_vectordb
def test_search_returns_scored_results():
    result = retriever.search("best cultural experiences in Kyoto", top_k=3)
    assert result["count"] > 0
    for item in result["results"]:
        assert item["text"]
        assert 0.0 <= item["score"] <= 1.0
        assert item["source"]


@requires_llm
@requires_vectordb
def test_search_honours_exact_filters():
    result = retriever.search("temples and shrines", destination="Kyoto",
                              category="culture", top_k=3)
    assert result["filter_strategy"] == "exact"
    for item in result["results"]:
        assert item["destination"] == "Kyoto"
        assert item["category"] == "culture"


@requires_llm
@requires_vectordb
def test_top_k_caps_result_count():
    result = retriever.search("things to do", top_k=2)
    assert result["count"] <= 2


@requires_llm
@requires_vectordb
def test_country_named_as_destination_relaxes_to_country():
    """'Japan' is a country in the metadata, not a destination city."""
    result = retriever.search("top attractions", destination="Japan",
                              category="attractions", top_k=5)
    assert result["count"] > 0
    assert result["filter_strategy"] == "destination_as_country"
    assert all(item["country"] == "Japan" for item in result["results"])
    assert "note" in result


@requires_llm
@requires_vectordb
def test_unknown_destination_falls_back_to_unfiltered():
    result = retriever.search("ancient temples", destination="Atlantis", top_k=2)
    assert result["count"] > 0
    assert result["filter_strategy"] == "unfiltered"
    assert "note" in result


@requires_llm
@requires_vectordb
def test_list_destinations_covers_all_cities():
    result = retriever.list_destinations()
    assert result["count"] >= 20
    names = {d["destination"] for d in result["destinations"]}
    assert {"Tokyo", "Kyoto", "Paris", "London", "Rome"} <= names


# ---------------- live MCP transport ----------------
@requires_mcp1
@requires_llm
@pytest.mark.asyncio
async def test_knowledge_tool_over_streamable_http():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(settings.mcp1_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert {"search_travel_knowledge", "list_destinations",
                    "list_categories"} <= names

            result = await session.call_tool(
                "search_travel_knowledge",
                {"query": "getting around Tokyo", "destination": "Tokyo",
                 "category": "transportation", "top_k": 2},
            )
            payload = json.loads(result.content[0].text)
            assert payload["count"] > 0
