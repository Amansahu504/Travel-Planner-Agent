"""Tests for MCP Server 3 — travel policy resources."""
from __future__ import annotations

import json

import pytest

from common.config import settings
from mcp_server_3 import resources
from tests.conftest import requires_mcp3

EXPECTED_TOPICS = {
    "visa", "passport", "insurance", "baggage", "hotel-cancellation",
    "flight-cancellation", "refund", "transportation", "safety",
    "booking-modification",
}


def test_all_ten_policies_registered():
    assert set(resources.POLICIES) == EXPECTED_TOPICS


def test_every_policy_file_exists_and_is_substantial():
    for topic in resources.POLICIES:
        text = resources.read_policy(topic)
        assert len(text) > 2000, f"{topic} policy is too short"


def test_every_policy_is_labelled_as_demo():
    """Fabricated policies must never look like real official policy."""
    for topic in resources.POLICIES:
        text = resources.read_policy(topic).lower()
        assert "demo" in text
        assert "fictional" in text


def test_metadata_has_required_fields():
    for topic in resources.POLICIES:
        meta = resources.metadata(topic)
        for field in ("policy_name", "category", "destination", "version",
                      "effective_date", "source", "uri"):
            assert meta.get(field), f"{topic} missing {field}"


def test_uri_scheme():
    assert resources.uri_for("visa") == "travel://policies/visa"


def test_index_covers_every_policy():
    assert len(resources.index()) == len(EXPECTED_TOPICS)


@pytest.mark.parametrize("question,expected", [
    ("what is the hotel cancellation policy?", "hotel-cancellation"),
    ("how much baggage can I bring in economy?", "baggage"),
    ("do I need a visa for Japan?", "visa"),
    ("how long does a refund take?", "refund"),
    ("does my passport need six months validity?", "passport"),
    ("what does travel insurance cover?", "insurance"),
    ("can I change my booking dates?", "booking-modification"),
    ("is it safe to travel there?", "safety"),
    ("how do I get from the airport to the hotel?", "transportation"),
    ("my flight was cancelled, what now?", "flight-cancellation"),
])
def test_find_policy_matches_expected_topic(question, expected):
    matches = resources.find_policy(question)
    assert matches, f"no match for {question!r}"
    assert expected in [m["topic"] for m in matches]


def test_find_policy_returns_empty_for_unrelated_question():
    assert resources.find_policy("what is the capital of France?") == []


def test_find_policy_respects_limit():
    assert len(resources.find_policy("cancellation refund policy", limit=2)) <= 2


def test_read_unknown_policy_raises():
    with pytest.raises(KeyError):
        resources.read_policy("nonexistent-policy")


# ---------------- live MCP transport ----------------
@requires_mcp3
@pytest.mark.asyncio
async def test_resources_and_tools_over_streamable_http():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(settings.mcp3_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Resources: index + one per policy.
            listed = await session.list_resources()
            uris = {str(r.uri) for r in listed.resources}
            assert "travel://policies/index" in uris
            for topic in EXPECTED_TOPICS:
                assert f"travel://policies/{topic}" in uris

            got = await session.read_resource("travel://policies/visa")
            assert "Visa Policy" in got.contents[0].text

            # Tools.
            result = await session.call_tool("get_policy",
                                             {"topic": "hotel-cancellation"})
            payload = json.loads(result.content[0].text)
            assert payload["policy_name"] == "Hotel Cancellation Policy (Demo)"
            assert "disclaimer" in payload

            bad = await session.call_tool("get_policy", {"topic": "nope"})
            assert "error" in json.loads(bad.content[0].text)
