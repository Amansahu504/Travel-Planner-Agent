"""Single source of truth for LLM + embedding model construction.

All agents use Google Gemini. Swapping providers later means editing only this
file. Each framework needs the model wrapped in its own way, so we expose one
factory per framework.
"""
from __future__ import annotations

import os

from common.config import settings

# Make sure downstream SDKs (google-genai, langchain, agno) see the key even if
# the process was started without exporting it.
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")


# ---- LangChain (Remote Agent 1: LangGraph) ----
def langchain_llm(pro: bool = False, temperature: float = 0.0):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.llm_model_pro if pro else settings.llm_model,
        temperature=temperature,
        max_retries=6,  # backoff on free-tier 429 rate limits
    )


def langchain_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=settings.embed_model)


# Free-tier Gemini enforces per-minute request quotas; every entry point below
# retries 429s with exponential backoff so a burst of agent calls doesn't fail
# the whole request.
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
RETRY_ATTEMPTS = 6


def _retry_options():
    from google.genai import types

    return types.HttpRetryOptions(
        attempts=RETRY_ATTEMPTS,
        initial_delay=2.0,
        max_delay=60.0,
        exp_base=2.0,
        jitter=1.0,
        http_status_codes=RETRY_STATUS_CODES,
    )


# ---- Agno (Remote Agent 2: workflow) ----
def agno_model(pro: bool = False):
    from agno.models.google import Gemini
    from google.genai import types

    return Gemini(
        id=settings.llm_model_pro if pro else settings.llm_model,
        client_params={"http_options": types.HttpOptions(
            retry_options=_retry_options()
        )},
    )


# ---- Google ADK (Host router) ----
def adk_model(pro: bool = False):
    """Return an ADK Gemini model configured with free-tier-friendly retries.

    ADK also accepts a bare model-id string, but that path has no retry policy,
    so a single 429 fails the whole host turn.
    """
    from google.adk.models.google_llm import Gemini

    return Gemini(
        model=settings.llm_model_pro if pro else settings.llm_model,
        retry_options=_retry_options(),
    )
