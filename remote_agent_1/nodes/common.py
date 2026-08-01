"""Shared helpers for the LangGraph nodes."""
from __future__ import annotations

from common.llm import langchain_llm


def content_text(resp) -> str:
    """Flatten a LangChain message's content to plain text.

    Some Gemini models return content as a list of reasoning/text blocks rather
    than a plain string.
    """
    content = getattr(resp, "content", resp)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type", "text") == "text" and item.get("text"):
                    parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


async def structured(schema, messages, *, pro: bool = False, temperature: float = 0.0):
    """Invoke the LLM with a Pydantic structured-output schema.

    Returns None when the model fails to produce a valid object, so callers can
    fall back instead of crashing (spec: validate all LLM structured outputs).
    """
    llm = langchain_llm(pro=pro, temperature=temperature).with_structured_output(schema)
    try:
        result = await llm.ainvoke(messages)
    except Exception:
        return None
    return result if isinstance(result, schema) else None


async def text(messages, *, pro: bool = False, temperature: float = 0.0) -> str:
    """Invoke the LLM for free-form text, returning "" on failure."""
    llm = langchain_llm(pro=pro, temperature=temperature)
    try:
        resp = await llm.ainvoke(messages)
    except Exception as exc:
        return f"(LLM call failed: {exc})"
    return content_text(resp).strip()


def trace(state, message: str) -> list[str]:
    """Append a high-level trace line (no chain-of-thought) for the UI."""
    return list(state.get("trace", [])) + [message]
