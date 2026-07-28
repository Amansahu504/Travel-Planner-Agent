"""MCP Server 3 — Travel Policy Server (streamable-http, port 8003).

Publishes 10 demo travel-policy documents as MCP **resources** under the
`travel://policies/...` URI scheme, plus agent-friendly **tools** (LLM clients
discover tools far more reliably than resources, so both are offered).

Every document is a clearly-labelled FICTIONAL demo policy — not real
government, airline, or hotel policy.

Run: uv run python -m mcp_server_3.main
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from common.config import settings
from common.logging_utils import get_logger, log_event
from mcp_server_3 import resources

logger = get_logger("mcp3")

mcp = FastMCP(
    "travel-policies",
    instructions=(
        "Authoritative source for this demo system's travel policies: visa, "
        "passport, insurance, baggage, hotel cancellation, flight cancellation, "
        "refunds, transportation, safety, and booking modification. All "
        "documents are FICTIONAL demo policies issued by a made-up company — "
        "never present them as real government or airline policy."
    ),
    host=settings.host,
    port=settings.mcp3_port,
)


# ---------------- Resources ----------------
@mcp.resource(
    "travel://policies/index",
    name="Travel Policy Index",
    description="List of all available demo travel policy documents with metadata.",
    mime_type="text/markdown",
)
def policy_index() -> str:
    lines = ["# Travel Policy Index (Demo)", ""]
    for meta in resources.index():
        lines.append(
            f"- `{meta['uri']}` — **{meta['policy_name']}** "
            f"(category: {meta['category']}, version {meta['version']}, "
            f"effective {meta['effective_date']})"
        )
    return "\n".join(lines)


def _register_policy_resource(topic: str) -> None:
    """Register one policy document as an MCP resource at travel://policies/<topic>.

    FastMCP requires the reader's signature to match the URI template's
    parameters — for these static URIs that means zero arguments, so `topic` is
    captured in the closure rather than passed as a default argument.
    """
    meta = resources.metadata(topic)

    def reader() -> str:
        log_event(logger, "resource_read", topic=topic)
        return resources.read_policy(topic)

    reader.__name__ = f"policy_{topic.replace('-', '_')}"
    mcp.resource(
        meta["uri"],
        name=meta["policy_name"],
        description=(f"{meta['policy_name']} — category {meta['category']}, "
                     f"version {meta['version']}, effective {meta['effective_date']}. "
                     f"Fictional demo document."),
        mime_type="text/markdown",
    )(reader)


for _topic in resources.POLICIES:
    _register_policy_resource(_topic)


# ---------------- Tools (agent-friendly wrappers) ----------------
@mcp.tool(annotations={"title": "List Travel Policies", "readOnlyHint": True})
def list_policies() -> dict:
    """List every available demo travel policy with its topic key and metadata.

    Call this first if you are unsure which policy topic answers the question.
    """
    items = resources.index()
    return {"count": len(items), "policies": items}


@mcp.tool(annotations={"title": "Get Travel Policy", "readOnlyHint": True})
def get_policy(topic: str) -> dict:
    """Return the full markdown text of one demo travel policy.

    Args:
        topic: One of "visa", "passport", "insurance", "baggage",
            "hotel-cancellation", "flight-cancellation", "refund",
            "transportation", "safety", "booking-modification".
    """
    key = (topic or "").strip().lower()
    if key not in resources.POLICIES:
        return {"error": f"Unknown topic '{topic}'.",
                "valid_topics": list(resources.POLICIES)}
    try:
        content = resources.read_policy(key)
    except FileNotFoundError as exc:
        log_event(logger, "resource_missing", topic=key)
        return {"error": str(exc)}

    log_event(logger, "tool_call", tool="get_policy", topic=key)
    return {**resources.metadata(key), "content": content,
            "disclaimer": "FICTIONAL demo policy — not real government, airline, "
                          "or hotel policy. Verify with official sources."}


@mcp.tool(annotations={"title": "Find Relevant Policy", "readOnlyHint": True})
def find_policy(question: str, limit: int = 3) -> dict:
    """Find which demo policies are most relevant to a natural-language question.

    Returns ranked matches (metadata only, no body text) — follow up with
    `get_policy` on the best topic to read the document.

    Args:
        question: The user's policy question, e.g. "what if I cancel my hotel?"
        limit: Maximum number of matches to return (default 3).
    """
    matches = resources.find_policy(question, limit)
    log_event(logger, "tool_call", tool="find_policy",
              question=question, matches=[m["topic"] for m in matches])
    if not matches:
        return {"count": 0, "matches": [],
                "message": "No policy matched. Call list_policies to see all topics.",
                "valid_topics": list(resources.POLICIES)}
    return {"count": len(matches), "matches": matches}


if __name__ == "__main__":
    print(f"Travel Policy MCP server on {settings.mcp3_url}")
    print(f"  {len(resources.POLICIES)} policy resources registered")
    mcp.run(transport="streamable-http")
