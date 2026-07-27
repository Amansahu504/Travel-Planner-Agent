"""Remote Agent 2 — Travel Operations Agent, hosted as an A2A server (port 9002).

Wraps the Agno workflow in an A2A executor and publishes its AgentCard at
/.well-known/agent-card.json.

Run: uv run python -m remote_agent_2.main
(Requires MCP Servers 2 and 3 running.)
"""
from __future__ import annotations

from common.a2a_server import serve
from common.config import settings
from common.logging_utils import get_logger, log_event
from remote_agent_2.a2a_server import AGENT_CARD
from remote_agent_2.workflow import answer

logger = get_logger("agent2")


def main() -> None:
    log_event(logger, "agent_starting", agent="travel-operations",
              port=settings.workflow_agent_port, mcp2=settings.mcp2_url,
              mcp3=settings.mcp3_url)
    serve(AGENT_CARD, answer, settings.host, settings.workflow_agent_port)


if __name__ == "__main__":
    main()
