"""Async wrapper around the ADK Runner for the host router agent.

Keeps one ADK session per HostRunner instance so a Gradio chat has continuity,
and inspects the run's events to build a high-level execution trace:
  * which remote A2A agents the host actually invoked (the real routing decision)
  * which internal steps each remote agent reported

Only high-level status is surfaced. Model reasoning is never exposed.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from common.logging_utils import get_logger, log_event, new_request_id
from host_agent.router import root_agent

logger = get_logger("host.runner")

APP_NAME = "travel_host"

AGENT_LABELS = {
    "travel_intelligence_agent": "Remote Agent 1 — Travel Intelligence (LangGraph)",
    "travel_operations_agent": "Remote Agent 2 — Travel Operations (Agno)",
}

# Remote Agent 1 appends its internal trace after this marker.
TRACE_MARKER = "<!--TRACE-->"


@dataclass
class HostResult:
    """A single host turn: the answer plus everything the UI needs to show."""
    answer: str
    trace: list[str] = field(default_factory=list)
    agents_called: list[str] = field(default_factory=list)
    request_id: str = ""
    error: str | None = None


def _strip_trace(text: str) -> tuple[str, list[str]]:
    """Split an agent reply into visible answer and its internal trace lines."""
    if TRACE_MARKER not in text:
        return text, []
    body, _, trace_block = text.partition(TRACE_MARKER)
    lines = [
        re.sub(r"^[-*]\s*", "", line).strip()
        for line in trace_block.strip().splitlines()
        if line.strip()
    ]
    return body.strip(), lines


class HostRunner:
    def __init__(self, user_id: str = "user"):
        self.user_id = user_id
        self.session_id = f"s-{uuid.uuid4().hex[:8]}"
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            app_name=APP_NAME,
            agent=root_agent,
            session_service=self.session_service,
        )
        self._ready = False

    async def _ensure_session(self) -> None:
        if not self._ready:
            await self.session_service.create_session(
                app_name=APP_NAME, user_id=self.user_id, session_id=self.session_id
            )
            self._ready = True

    async def ask(self, query: str) -> HostResult:
        """Run one host turn, returning the answer plus an execution trace."""
        request_id = new_request_id()
        log_event(logger, "host_request", request_id=request_id, query=query)

        if not query or not query.strip():
            return HostResult(answer="Please enter a travel request.",
                              request_id=request_id)

        await self._ensure_session()
        message = types.Content(role="user", parts=[types.Part(text=query)])

        trace: list[str] = ["Gradio UI received the request",
                            "Host Router (Google ADK) analysing the request"]
        agents_called: list[str] = []
        final_text = ""

        try:
            async for event in self.runner.run_async(
                user_id=self.user_id,
                session_id=self.session_id,
                new_message=message,
            ):
                content = getattr(event, "content", None)
                if content and getattr(content, "parts", None):
                    for part in content.parts:
                        # Outbound delegation: the host invoked a remote agent.
                        call = getattr(part, "function_call", None)
                        if call is not None and call.name in AGENT_LABELS:
                            if call.name not in agents_called:
                                agents_called.append(call.name)
                            trace.append(f"A2A call → {AGENT_LABELS[call.name]}")
                            log_event(logger, "a2a_delegation",
                                      request_id=request_id, agent=call.name)

                        # Inbound result: unpack the remote agent's own trace.
                        response = getattr(part, "function_response", None)
                        if response is not None and response.name in AGENT_LABELS:
                            trace.append(f"Response received from "
                                         f"{AGENT_LABELS[response.name]}")
                            payload = getattr(response, "response", None)
                            for line in _remote_trace_lines(payload):
                                trace.append(f"    ↳ {line}")

                if event.is_final_response() and content and content.parts:
                    final_text = "".join(
                        part.text for part in content.parts
                        if getattr(part, "text", None)
                    )
        except Exception as exc:
            log_event(logger, "host_request_failed", request_id=request_id,
                      error=f"{type(exc).__name__}: {exc}")
            return HostResult(
                answer=("I could not reach the travel agents to complete that "
                        "request. Please check that all services are running and "
                        "try again."),
                trace=trace + ["Host request failed"],
                agents_called=agents_called,
                request_id=request_id,
                error=f"{type(exc).__name__}: {exc}",
            )

        answer, _ = _strip_trace(final_text)
        if not answer.strip():
            answer = ("I did not get a usable response from the travel agents. "
                      "Please try rephrasing your request.")

        trace.append("Host Router consolidated the final response")
        log_event(logger, "host_request_complete", request_id=request_id,
                  agents=agents_called or ["none"], chars=len(answer))

        return HostResult(answer=answer, trace=trace,
                          agents_called=agents_called, request_id=request_id)


def _remote_trace_lines(payload) -> list[str]:
    """Pull a remote agent's internal trace out of a function_response payload."""
    if payload is None:
        return []
    text = ""
    if isinstance(payload, dict):
        for key in ("result", "response", "output", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                text = value
                break
        else:
            text = str(payload)
    else:
        text = str(payload)

    _, lines = _strip_trace(text)
    return lines


async def ask_once(query: str) -> HostResult:
    """One-shot helper for CLI tests."""
    return await HostRunner().ask(query)
