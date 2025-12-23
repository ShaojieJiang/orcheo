from __future__ import annotations
import json
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from orcheo_backend.app.routers import triggers


def test_parse_webhook_body_preserves_raw_payload_and_parsed_body() -> None:
    """Raw and parsed payloads are preserved when requested."""

    raw_body = b'{"key": "value"}'
    payload, parsed_body = triggers._parse_webhook_body(
        raw_body, preserve_raw_body=True
    )

    assert payload["raw"] == raw_body.decode("utf-8")
    assert payload["parsed"] == {"key": "value"}
    assert parsed_body == {"key": "value"}


def test_maybe_handle_slack_url_verification_returns_challenge_payload() -> None:
    """Slack URL verification requests are answered with the challenge."""

    response = triggers._maybe_handle_slack_url_verification(
        {"type": "url_verification", "challenge": "test-challenge"}
    )

    assert isinstance(response, JSONResponse)
    assert json.loads(response.body) == {"challenge": "test-challenge"}


def test_maybe_handle_slack_url_verification_rejects_missing_challenge() -> None:
    """Missing Slack challenge values raise an HTTPException."""

    with pytest.raises(HTTPException) as exc_info:
        triggers._maybe_handle_slack_url_verification(
            {"type": "url_verification", "challenge": ""}
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Missing Slack challenge value"


def test_parse_webhook_body_returns_raw_when_not_preserving_bad_json() -> None:
    """When not preserving, invalid JSON payloads surface as bytes."""

    raw_body = b"not-json"
    payload, parsed_body = triggers._parse_webhook_body(
        raw_body, preserve_raw_body=False
    )

    assert payload == raw_body
    assert parsed_body is None


def test_parse_webhook_body_preserves_non_mapping_parsed_payload() -> None:
    """Lists or other non-mappings are preserved but not returned as parsed_body."""

    raw_body = b'["value", 123]'
    payload, parsed_body = triggers._parse_webhook_body(
        raw_body, preserve_raw_body=True
    )

    assert payload["raw"] == raw_body.decode("utf-8")
    assert payload["parsed"] == ["value", 123]
    assert parsed_body is None
