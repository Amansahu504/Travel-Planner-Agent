"""Build the Chroma vector DB from the destination knowledge documents.

Each markdown guide in data/knowledge/ is split by `## Section` heading so a
chunk maps cleanly to one knowledge category (attractions, food, culture, ...).
Long sections are further split. Every chunk is stored with rich metadata used
by MCP Server 1 for filtering:

    destination, country, category, season, source, language, tags

Run after generating data:
    uv run python -m scripts.generate_data
    uv run python -m ingest.build_vectordb
"""
from __future__ import annotations

import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from common.config import KNOWLEDGE_DIR
from common.vectordb import (
    COLLECTION_NAME, embed_documents_throttled, get_client,
)
from scripts.destinations import DESTINATIONS

# Heading text -> canonical category slug.
CATEGORY_MAP = {
    "attractions": "attractions",
    "food": "food",
    "culture": "culture",
    "transportation": "transportation",
    "safety": "safety",
    "accommodation": "accommodation",
    "activities": "activities",
    "weather": "weather",
    "local customs": "local_customs",
    "budget planning notes": "budget",
    "suggested pace": "planning",
}

# Categories whose content is season-specific in our generated guides.
SEASONAL = {"weather"}


def parse_sections(text: str) -> list[tuple[str, str]]:
    """Split a markdown doc into (heading, body) pairs on '## ' headings."""
    parts = re.split(r"^## +(.+)$", text, flags=re.MULTILINE)
    # parts = [preamble, heading1, body1, heading2, body2, ...]
    sections = []
    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip()
        body = parts[i + 1].strip()
        if body:
            sections.append((heading, body))
    return sections


def build() -> None:
    docs_paths = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not docs_paths:
        raise SystemExit(
            f"No knowledge documents in {KNOWLEDGE_DIR}. "
            "Run: uv run python -m scripts.generate_data"
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900, chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []

    for path in docs_paths:
        text = path.read_text(encoding="utf-8")
        # Recover destination/country from the curated table.
        city = None
        for candidate in DESTINATIONS:
            if candidate.lower().replace(" ", "_") == path.stem:
                city = candidate
                break
        if city is None:
            print(f"  ! skipping {path.name}: unknown destination")
            continue
        info = DESTINATIONS[city]
        country = info["country"]
        tags = ",".join(info["themes"])  # Chroma metadata must be scalar

        for heading, body in parse_sections(text):
            category = CATEGORY_MAP.get(heading.strip().lower(), "general")
            season = "october" if category in SEASONAL else "all"
            for j, chunk in enumerate(splitter.split_text(body)):
                slug = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")
                ids.append(f"{path.stem}__{slug}__{j}")
                # Prefix the chunk with its context so embeddings capture the
                # destination even when the body text doesn't name it.
                docs.append(f"{city}, {country} — {heading}\n\n{chunk}")
                metas.append({
                    "destination": city,
                    "country": country,
                    "category": category,
                    "season": season,
                    "source": f"{city} Destination Guide (Demo)",
                    "language": "en",
                    "tags": tags,
                })
        print(f"  parsed {path.name}  ({city}, {country})")

    client = get_client()

    # Resume support: an interrupted run (or a free-tier quota stall) leaves the
    # collection partially filled. Skip chunk ids that are already stored rather
    # than re-embedding everything.
    collection = client.get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    existing: set[str] = set()
    if collection.count():
        existing = set(collection.get(include=[]).get("ids") or [])
        if existing:
            print(f"\nCollection already holds {len(existing)} chunks — resuming.")

    todo = [(i, d, m) for i, d, m in zip(ids, docs, metas) if i not in existing]
    if not todo:
        print(f"Nothing to do. Collection '{COLLECTION_NAME}' holds "
              f"{collection.count()} chunks.")
        return

    print(f"\nEmbedding {len(todo)} chunks with Gemini "
          f"(throttled for the free-tier limit; this takes a few minutes)...")

    todo_ids = [t[0] for t in todo]
    todo_docs = [t[1] for t in todo]
    todo_metas = [t[2] for t in todo]

    # Embed and persist in slices so an interruption keeps completed work.
    SLICE = 60
    for start in range(0, len(todo_docs), SLICE):
        chunk_ids = todo_ids[start:start + SLICE]
        chunk_docs = todo_docs[start:start + SLICE]
        chunk_metas = todo_metas[start:start + SLICE]
        vectors = embed_documents_throttled(chunk_docs, progress=print)
        collection.add(
            ids=chunk_ids, documents=chunk_docs,
            embeddings=vectors, metadatas=chunk_metas,
        )
        print(f"  stored {min(start + SLICE, len(todo_docs))}/{len(todo_docs)}")

    print(f"Done. Collection '{COLLECTION_NAME}' holds {collection.count()} chunks.")


if __name__ == "__main__":
    build()
