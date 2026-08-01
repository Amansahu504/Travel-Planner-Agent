"""Structured, key=value logging used across all services.

Never logs API keys or full user PII. Each service calls `get_logger(name)` and
emits events with `log_event(logger, event, **fields)` so the trace is greppable
and consistent (request_id, routing decision, mcp tool, relevance, etc.).
"""
from __future__ import annotations

import logging
import os
import sys
import uuid

_CONFIGURED = False
_REDACT_KEYS = {"api_key", "google_api_key", "tavily_api_key", "authorization", "token"}


def enable_utf8_stdout() -> None:
    """Force UTF-8 on stdout/stderr.

    The Windows console defaults to cp1252, which raises UnicodeEncodeError the
    moment a log line or LLM response contains an em dash, arrow, or non-Latin
    script. Replacing unencodable characters is better than crashing a service.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    enable_utf8_stdout()
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    # Quiet noisy third-party loggers.
    for noisy in ("httpx", "httpcore", "uvicorn.access", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)


def new_request_id() -> str:
    return uuid.uuid4().hex[:8]


def _fmt(value) -> str:
    text = str(value).replace("\n", " ")
    if len(text) > 200:
        text = text[:197] + "..."
    if " " in text or "=" in text:
        text = '"' + text.replace('"', "'") + '"'
    return text


def log_event(logger: logging.Logger, event: str, **fields) -> None:
    parts = [f"event={event}"]
    for key, value in fields.items():
        if key.lower() in _REDACT_KEYS:
            value = "[REDACTED]"
        parts.append(f"{key}={_fmt(value)}")
    logger.info(" ".join(parts))
