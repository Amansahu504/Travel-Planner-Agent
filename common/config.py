"""Central configuration loaded from .env. Import `settings` everywhere.

Service URLs are derived from HOST + port for local runs, but every URL can be
overridden with an environment variable (MCP1_URL, RAG_AGENT_URL, ...) which is
what docker-compose does so containers talk over service names instead of
localhost.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---- filesystem layout ----
DATA = ROOT / "data"
KNOWLEDGE_DIR = DATA / "knowledge"        # destination knowledge docs (MCP 1 -> vectors)
POLICY_DOCS_DIR = DATA / "policies"       # travel policy markdown (MCP 3 resources)
CHROMA_DIR = DATA / "chroma"              # vector store
SEED_DIR = DATA / "seed"                  # CSV seed data for SQLite
TRAVEL_DB = DATA / "travel.db"            # SQLite operational DB (MCP 2)

FLIGHTS_CSV = SEED_DIR / "flights.csv"
HOTELS_CSV = SEED_DIR / "hotels.csv"
ACTIVITIES_CSV = SEED_DIR / "activities.csv"
BOOKINGS_CSV = SEED_DIR / "bookings.csv"


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    # tolerate inline comments in .env, e.g. "8001   # retriever"
    return int(str(raw).split("#")[0].strip())


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default) or default


@dataclass(frozen=True)
class Settings:
    host: str = _env("HOST", "127.0.0.1")

    # ---- LLM ----
    google_api_key: str = _env("GOOGLE_API_KEY")
    tavily_api_key: str = _env("TAVILY_API_KEY")
    llm_model: str = _env("LLM_MODEL", "gemini-flash-lite-latest")
    llm_model_pro: str = _env("LLM_MODEL_PRO", "gemini-flash-lite-latest")
    embed_model: str = _env("EMBED_MODEL", "models/gemini-embedding-001")

    # ---- flight provider (Duffel test mode, optional) ----
    duffel_api_key: str = _env("DUFFEL_API_KEY")
    # auto = use Duffel when a key is present, else the synthetic database.
    # Force with "demo" or "duffel".
    flight_provider: str = _env("FLIGHT_PROVIDER", "auto").strip().lower()
    duffel_version: str = _env("DUFFEL_VERSION", "v2")

    # ---- ports ----
    mcp1_port: int = _int("MCP1_PORT", 8001)
    mcp2_port: int = _int("MCP2_PORT", 8002)
    mcp3_port: int = _int("MCP3_PORT", 8003)
    rag_agent_port: int = _int("RAG_AGENT_PORT", 9001)
    workflow_agent_port: int = _int("WORKFLOW_AGENT_PORT", 9002)
    ui_port: int = _int("UI_PORT", 7860)

    # ---- workflow guards ----
    max_retrieval_retries: int = _int("MAX_RETRIEVAL_RETRIES", 2)
    max_revisions: int = _int("MAX_REVISIONS", 3)

    # ---- URLs (env override wins; otherwise derived) ----
    # MCP streamable-http transport mounts the endpoint under /mcp.
    @property
    def mcp1_url(self) -> str:
        return _env("MCP1_URL") or f"http://{self._client_host}:{self.mcp1_port}/mcp"

    @property
    def mcp2_url(self) -> str:
        return _env("MCP2_URL") or f"http://{self._client_host}:{self.mcp2_port}/mcp"

    @property
    def mcp3_url(self) -> str:
        return _env("MCP3_URL") or f"http://{self._client_host}:{self.mcp3_port}/mcp"

    @property
    def rag_agent_url(self) -> str:
        return _env("RAG_AGENT_URL") or f"http://{self._client_host}:{self.rag_agent_port}"

    @property
    def workflow_agent_url(self) -> str:
        return (_env("WORKFLOW_AGENT_URL")
                or f"http://{self._client_host}:{self.workflow_agent_port}")

    @property
    def _client_host(self) -> str:
        """Host to dial when *connecting* to a peer service.

        Servers bind 0.0.0.0 in Docker, but you can never *connect* to 0.0.0.0,
        so fall back to localhost for outbound URLs.
        """
        return "127.0.0.1" if self.host in ("0.0.0.0", "", None) else self.host

    @property
    def llm_configured(self) -> bool:
        key = self.google_api_key
        return bool(key) and "your_" not in key

    @property
    def duffel_configured(self) -> bool:
        key = self.duffel_api_key
        return bool(key) and key.startswith("duffel_") and "your_" not in key

    @property
    def use_duffel_flights(self) -> bool:
        """Whether flight tools should hit Duffel (vs the synthetic database)."""
        if self.flight_provider == "demo":
            return False
        if self.flight_provider == "duffel":
            return True
        return self.duffel_configured  # "auto"


settings = Settings()
