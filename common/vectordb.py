"""Shared Chroma vector-store access for the travel-knowledge base.

Used by ingestion (ingest/build_vectordb.py) and MCP Server 1 (the retriever).
Documents carry rich metadata (destination, country, category, season, source,
language, tags) so the retriever can apply metadata filters.
"""
from __future__ import annotations

import time

import chromadb

from common.config import CHROMA_DIR
from common.llm import langchain_embeddings

COLLECTION_NAME = "travel_knowledge"

# Categories used across the knowledge base + retriever filtering.
CATEGORIES = [
    "attractions", "food", "culture", "transportation", "safety",
    "accommodation", "activities", "weather", "local_customs",
]

_embeddings = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = langchain_embeddings()
    return _embeddings


def get_client() -> chromadb.ClientAPI:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(create: bool = False):
    client = get_client()
    if create:
        return client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
    return client.get_collection(COLLECTION_NAME)


def collection_exists() -> bool:
    try:
        get_collection()
        return True
    except Exception:
        return False


# ---- rate-limited embedding ----
# The Gemini free tier allows ~100 embed_content requests per minute, and
# langchain issues one request per document. Ingesting a few hundred chunks
# therefore needs throttling plus retry, or the whole build dies on a 429.
EMBED_BATCH = 20          # documents per embed_documents() call
EMBED_PAUSE_SECONDS = 14.0  # sleep between batches -> ~85 requests/minute


def _is_rate_limit(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


def embed_documents_throttled(
    texts: list[str],
    *,
    batch_size: int = EMBED_BATCH,
    pause: float = EMBED_PAUSE_SECONDS,
    max_retries: int = 6,
    progress=None,
) -> list[list[float]]:
    """Embed `texts` staying inside the free-tier rate limit.

    Batches are embedded with a pause in between; a 429 triggers exponential
    backoff and a retry of just that batch, so a long ingest survives a
    transient quota bump instead of losing all prior work.
    """
    embeddings = get_embeddings()
    vectors: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        delay = 20.0
        for attempt in range(1, max_retries + 1):
            try:
                vectors.extend(embeddings.embed_documents(batch))
                break
            except Exception as exc:
                if not _is_rate_limit(exc) or attempt == max_retries:
                    raise
                if progress:
                    progress(f"    rate limited; waiting {delay:.0f}s "
                             f"(attempt {attempt}/{max_retries})")
                time.sleep(delay)
                delay = min(delay * 1.6, 90.0)
        if progress:
            progress(f"    embedded {len(vectors)}/{len(texts)} chunks")
        if start + batch_size < len(texts):
            time.sleep(pause)

    return vectors
