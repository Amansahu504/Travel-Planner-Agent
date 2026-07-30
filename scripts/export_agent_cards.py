"""Export both remote agents' A2A agent cards to JSON files.

The live cards are always served at /.well-known/agent-card.json; these files
exist for documentation and inspection without running the services. Generating
them from the same objects the servers publish keeps them from drifting.

Run: uv run python -m scripts.export_agent_cards
"""
from __future__ import annotations

import json
from pathlib import Path

from remote_agent_1.a2a_server import AGENT_CARD as CARD_1
from remote_agent_2.a2a_server import AGENT_CARD as CARD_2

ROOT = Path(__file__).resolve().parent.parent

TARGETS = [
    (CARD_1, ROOT / "remote_agent_1" / "agent_card.json"),
    (CARD_2, ROOT / "remote_agent_2" / "agent_card.json"),
]


def main() -> None:
    for card, path in TARGETS:
        payload = card.model_dump(mode="json", exclude_none=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"  wrote {path.relative_to(ROOT)}  ({card.name}, "
              f"{len(card.skills)} skills)")


if __name__ == "__main__":
    main()
