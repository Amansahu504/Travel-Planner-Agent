"""Semantic retrieval over the travel-knowledge vector store (MCP Server 1 core).

Kept separate from main.py so it can be unit-tested without starting a server.
"""
from __future__ import annotations

from typing import Optional

from common.logging_utils import get_logger, log_event
from common.vectordb import get_collection, get_embeddings

logger = get_logger("mcp1.retriever")


def build_where(
    destination: Optional[str] = None,
    category: Optional[str] = None,
    allowed_sources: Optional[list[str]] = None,
    country: Optional[str] = None,
) -> Optional[dict]:
    """Compose a Chroma `where` filter from optional metadata constraints."""
    clauses: list[dict] = []
    if destination:
        clauses.append({"destination": destination.strip().title()})
    if category:
        clauses.append({"category": category.strip().lower()})
    if country:
        clauses.append({"country": country.strip()})
    if allowed_sources:
        clauses.append({"source": {"$in": list(allowed_sources)}})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _run_query(collection, query_vec: list[float], top_k: int,
               where: Optional[dict]) -> list[dict]:
    res = collection.query(
        query_embeddings=[query_vec],
        n_results=max(1, int(top_k)),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    results = []
    for doc, meta, dist in zip(docs, metas, dists):
        meta = meta or {}
        results.append({
            "text": doc,
            "destination": meta.get("destination"),
            "country": meta.get("country"),
            "category": meta.get("category"),
            "season": meta.get("season"),
            "source": meta.get("source"),
            "language": meta.get("language"),
            "tags": (meta.get("tags") or "").split(",") if meta.get("tags") else [],
            "score": round(1.0 - float(dist), 4),  # cosine distance -> similarity
        })
    return results


def search(
    query: str,
    top_k: int = 5,
    destination: Optional[str] = None,
    category: Optional[str] = None,
    allowed_sources: Optional[list[str]] = None,
    country: Optional[str] = None,
) -> dict:
    """Run semantic search with optional metadata filtering.

    Filters are progressively relaxed rather than returning nothing:

    1. Exactly as asked.
    2. If empty and `destination` looks like a country (for example "Japan"),
       retry it as a country filter — the knowledge base is indexed by city, so
       a country-level request must fan out to that country's cities.
    3. If still empty, drop the category filter (the topic may be phrased
       differently).
    4. If still empty, fall back to unfiltered semantic search.

    The response reports which strategy produced the results so the caller knows
    how literally its filters were honoured.
    """
    if not query or not query.strip():
        return {"query": query, "count": 0, "results": [],
                "error": "query must be a non-empty string"}

    requested = {
        "destination": destination, "category": category,
        "country": country, "allowed_sources": allowed_sources,
    }
    active_filters = {k: v for k, v in requested.items() if v}

    try:
        collection = get_collection()
    except Exception as exc:
        log_event(logger, "retrieval_failed", reason="collection_missing", error=str(exc))
        return {
            "query": query, "count": 0, "results": [],
            "error": "Travel knowledge base is not built yet. "
                     "Run: uv run python -m ingest.build_vectordb",
        }

    try:
        query_vec = get_embeddings().embed_query(query)
    except Exception as exc:
        log_event(logger, "retrieval_failed", reason="embedding_error", error=str(exc))
        return {"query": query, "count": 0, "results": [],
                "error": f"Embedding failed: {exc}"}

    # Progressive relaxation strategies, tried in order.
    strategies: list[tuple[str, dict | None]] = [
        ("exact", build_where(destination, category, allowed_sources, country)),
    ]
    if destination:
        # "Japan" / "Italy" are countries in our metadata, not destinations.
        strategies.append((
            "destination_as_country",
            build_where(None, category, allowed_sources, destination),
        ))
    if category:
        strategies.append((
            "without_category",
            build_where(destination, None, allowed_sources, country),
        ))
        if destination:
            strategies.append((
                "country_without_category",
                build_where(None, None, allowed_sources, destination),
            ))
    strategies.append(("unfiltered", None))

    results: list[dict] = []
    used = "exact"
    seen_where: list[dict | None] = []
    for name, where in strategies:
        if where in seen_where:  # skip duplicate filter shapes
            continue
        seen_where.append(where)
        try:
            results = _run_query(collection, query_vec, top_k, where)
        except Exception as exc:
            log_event(logger, "retrieval_failed", reason="query_error",
                      strategy=name, error=str(exc))
            return {"query": query, "count": 0, "results": [],
                    "error": f"Vector search failed: {exc}"}
        if results:
            used = name
            break

    log_event(logger, "retrieval_complete", query=query, count=len(results),
              filters=active_filters or "none", strategy=used)

    payload = {
        "query": query,
        "filters_applied": active_filters,
        "filter_strategy": used,
        "count": len(results),
        "results": results,
        "data_source": "internal travel knowledge base (demo destination guides)",
    }
    if used != "exact" and active_filters:
        payload["note"] = (
            f"No match for the exact filters, so the search was relaxed "
            f"({used.replace('_', ' ')}). Check each result's destination before "
            f"relying on it."
        )
    return payload


def list_destinations() -> dict:
    """Distinct destinations/countries present in the knowledge base."""
    try:
        collection = get_collection()
    except Exception:
        return {"count": 0, "destinations": [],
                "error": "Knowledge base not built. Run: uv run python -m ingest.build_vectordb"}

    got = collection.get(include=["metadatas"])
    seen: dict[str, str] = {}
    for meta in got.get("metadatas") or []:
        if meta and meta.get("destination"):
            seen[meta["destination"]] = meta.get("country", "")
    items = [{"destination": d, "country": c} for d, c in sorted(seen.items())]
    return {"count": len(items), "destinations": items}
