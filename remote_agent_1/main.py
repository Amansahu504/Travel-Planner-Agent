"""Remote Agent 1 — Travel Intelligence Agent, hosted as an A2A server (port 9001).

Wraps the corrective/self-reflective LangGraph workflow in an A2A executor and
publishes its AgentCard at /.well-known/agent-card.json.

Run: uv run python -m remote_agent_1.main
(Requires MCP Server 1 and 3 running, and the vector DB built.)
"""
from __future__ import annotations

from common.a2a_server import serve
from common.config import settings
from common.logging_utils import get_logger, log_event
from remote_agent_1.a2a_server import AGENT_CARD
from remote_agent_1.graph import answer

logger = get_logger("agent1")


def main() -> None:
    log_event(logger, "agent_starting", agent="travel-intelligence",
              port=settings.rag_agent_port, mcp1=settings.mcp1_url,
              mcp3=settings.mcp3_url)
    serve(AGENT_CARD, answer, settings.host, settings.rag_agent_port)


if __name__ == "__main__":
    main()
