"""Tests for SlackEventsParserNode."""

from __future__ import annotations
import hashlib
import hmac
import json
import time
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.slack import SlackEventsParserNode


def _sign_slack(secret: str, timestamp: int, body: str) -> str:
    base = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _build_state(raw_body: str, headers: dict[str, str]) -> State:
    return State(
        messages=[], inputs={"body": {"raw": raw_body}, "headers": headers}, results={}
    )


@pytest.mark.asyncio
async def test_slack_events_parser_accepts_valid_event() -> None:
    secret = "slack-secret"
    timestamp = int(time.time())
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": "C123",
            "user": "U123",
            "text": "hello",
        },
    }
    raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    headers = {
        "x-slack-signature": _sign_slack(secret, timestamp, raw_body),
        "x-slack-request-timestamp": str(timestamp),
    }

    node = SlackEventsParserNode(
        name="slack_events_parser",
        signing_secret=secret,
        channel_id="C123",
        allowed_event_types=["app_mention"],
    )
    result = await node.run(_build_state(raw_body, headers), RunnableConfig())

    assert result["should_process"] is True
    assert result["event_type"] == "app_mention"
    assert result["channel"] == "C123"
    assert result["user"] == "U123"
    assert result["text"] == "hello"


@pytest.mark.asyncio
async def test_slack_events_parser_url_verification() -> None:
    secret = "slack-secret"
    timestamp = int(time.time())
    payload = {"type": "url_verification", "challenge": "abc"}
    raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    headers = {
        "x-slack-signature": _sign_slack(secret, timestamp, raw_body),
        "x-slack-request-timestamp": str(timestamp),
    }

    node = SlackEventsParserNode(name="slack_events_parser", signing_secret=secret)
    result = await node.run(_build_state(raw_body, headers), RunnableConfig())

    assert result["is_verification"] is True
    assert result["challenge"] == "abc"
    assert result["should_process"] is False


@pytest.mark.asyncio
async def test_slack_events_parser_channel_filter_blocks() -> None:
    secret = "slack-secret"
    timestamp = int(time.time())
    payload = {
        "type": "event_callback",
        "event": {"type": "app_mention", "channel": "C999"},
    }
    raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    headers = {
        "x-slack-signature": _sign_slack(secret, timestamp, raw_body),
        "x-slack-request-timestamp": str(timestamp),
    }

    node = SlackEventsParserNode(
        name="slack_events_parser",
        signing_secret=secret,
        channel_id="C123",
    )
    result = await node.run(_build_state(raw_body, headers), RunnableConfig())

    assert result["should_process"] is False
    assert result["event_type"] == "app_mention"


@pytest.mark.asyncio
async def test_slack_events_parser_rejects_invalid_signature() -> None:
    secret = "slack-secret"
    timestamp = int(time.time())
    payload = {
        "type": "event_callback",
        "event": {"type": "app_mention", "channel": "C123"},
    }
    raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    headers = {
        "x-slack-signature": _sign_slack("wrong", timestamp, raw_body),
        "x-slack-request-timestamp": str(timestamp),
    }

    node = SlackEventsParserNode(name="slack_events_parser", signing_secret=secret)

    with pytest.raises(ValueError, match="Slack signature verification failed"):
        await node.run(_build_state(raw_body, headers), RunnableConfig())
