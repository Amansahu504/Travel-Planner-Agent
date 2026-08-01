"""Reusable A2A server scaffolding shared by both remote agents.

Wraps any async `handler(query: str) -> str` in an A2A AgentExecutor and serves
it as a standards-compliant A2A server (Starlette + JSON-RPC) that publishes an
AgentCard at /.well-known/agent-card.json.
"""
from __future__ import annotations

import inspect
from typing import Awaitable, Callable, Union

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message, new_task

from common.logging_utils import enable_utf8_stdout

Handler = Callable[[str], Union[str, Awaitable[str]]]


class FunctionExecutor(AgentExecutor):
    """Adapts a plain async/sync string handler to the A2A executor interface."""

    def __init__(self, handler: Handler):
        self._handler = handler

    async def _run(self, query: str) -> str:
        result = self._handler(query)
        if inspect.isawaitable(result):
            result = await result
        return str(result)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        task = context.current_task
        if task is None:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()
        try:
            answer = await self._run(query)
        except Exception as exc:  # surface errors as a failed task
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(f"Agent error: {exc}"),
                final=True,
            )
            return

        await updater.add_artifact([Part(root=TextPart(text=answer))], name="response")
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("Cancellation is not supported by this agent.")


def make_agent_card(
    *,
    name: str,
    description: str,
    url: str,
    skills: list[AgentSkill],
    version: str = "1.0.0",
) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        url=url,
        version=version,
        default_input_modes=["text", "text/plain"],
        default_output_modes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=skills,
    )


def build_app(card: AgentCard, handler: Handler) -> A2AStarletteApplication:
    request_handler = DefaultRequestHandler(
        agent_executor=FunctionExecutor(handler),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(agent_card=card, http_handler=request_handler)


def serve(card: AgentCard, handler: Handler, host: str, port: int) -> None:
    enable_utf8_stdout()  # LLM responses routinely contain non-cp1252 characters
    app = build_app(card, handler)
    print(f"A2A agent '{card.name}' serving at http://{host}:{port}"
          f"  (card: http://{host}:{port}/.well-known/agent-card.json)")
    uvicorn.run(app.build(), host=host, port=port)
