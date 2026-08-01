"""MCP client wiring for Remote Agent 1.

Loads real MCP tools over streamable-HTTP with langchain-mcp-adapters:
  * MCP Server 1 (8001) — search_travel_knowledge, list_destinations
  * MCP Server 3 (8003) — find_policy, get_policy

Tools are cached after first load. Every call degrades gracefully: if a server
is down the caller gets an empty result plus an error string rather than an
exception, so the graph can continue (and fall back to web search).
"""
from __future__ import annotations

import json
from typing import Any

from common.config import settings
from common.logging_utils import get_logger, log_event

logger = get_logger("agent1.mcp")

_tools_cache: dict[str, Any] | None = None


async def _load_tools() -> dict[str, Any]:
    """Discover tools from MCP Servers 1 and 3 over streamable HTTP."""
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache

    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient({
        "travel_knowledge": {"url": settings.mcp1_url, "transport": "streamable_http"},
        "travel_policies": {"url": settings.mcp3_url, "transport": "streamable_http"},
    })
    tools = await client.get_tools()
    _tools_cache = {tool.name: tool for tool in tools}
    log_event(logger, "mcp_tools_loaded", tools=sorted(_tools_cache))
    return _tools_cache


def parse_tool_payload(raw) -> dict:
    """MCP tool results arrive as JSON text; normalise to a dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"results": parsed}
        except json.JSONDecodeError:
            return {"text": raw}
    if isinstance(raw, list):
        # Some adapters return a list of content blocks.
        for item in raw:
            if isinstance(item, dict) and item.get("text"):
                return parse_tool_payload(item["text"])
        return {"results": raw}
    return {"text": str(raw)}


async def call_tool(name: str, args: dict) -> dict:
    """Invoke an MCP tool by name, returning a dict (never raising)."""
    try:
        tools = await _load_tools()
    except Exception as exc:
        log_event(logger, "mcp_unavailable", tool=name, error=str(exc))
        return {"error": f"MCP servers unavailable: {exc}", "count": 0, "results": []}

    tool = tools.get(name)
    if tool is None:
        return {"error": f"MCP tool '{name}' not found. Available: {sorted(tools)}",
                "count": 0, "results": []}
    try:
        raw = await tool.ainvoke(args)
    except Exception as exc:
        log_event(logger, "mcp_tool_error", tool=name, error=str(exc))
        return {"error": f"MCP tool '{name}' failed: {exc}", "count": 0, "results": []}

    return parse_tool_payload(raw)


# ---- convenience wrappers used by the graph nodes ----
async def search_knowledge(query: str, top_k: int = 5, destination: str | None = None,
                           category: str | None = None) -> dict:
    args: dict[str, Any] = {"query": query, "top_k": top_k}
    if destination:
        args["destination"] = destination
    if category:
        args["category"] = category
    return await call_tool("search_travel_knowledge", args)


async def find_policy(question: str, limit: int = 2) -> dict:
    return await call_tool("find_policy", {"question": question, "limit": limit})


async def get_policy(topic: str) -> dict:
    return await call_tool("get_policy", {"topic": topic})
