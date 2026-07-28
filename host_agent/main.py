"""Host / Router entry point — launches the Gradio UI (port 7860).

Run: uv run python -m host_agent.main
(Requires the MCP servers and both remote agents to be running; use
`uv run python run_all.py` to start everything at once.)
"""
from __future__ import annotations

from common.config import settings
from common.logging_utils import get_logger, log_event
from host_agent.gradio_app import launch_ui

logger = get_logger("host")


def main() -> None:
    log_event(logger, "host_starting", port=settings.ui_port,
              agent1=settings.rag_agent_url, agent2=settings.workflow_agent_url)
    launch_ui()


if __name__ == "__main__":
    main()
