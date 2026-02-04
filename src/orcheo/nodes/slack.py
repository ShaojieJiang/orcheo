"""Slack node."""

import hashlib
import hmac
import json
import os
import time
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal
from fastmcp import Client
from fastmcp.client.transports import NpxStdioTransport
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, field_validator
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="SlackNode",
        description="Slack node",
        category="slack",
    )
)
class SlackNode(TaskNode):
    """Slack node.

    To use this node, you need to set the following environment variables:
    - SLACK_BOT_TOKEN: Required. The Bot User OAuth Token starting with xoxb-.
    - SLACK_TEAM_ID: Required. Your Slack workspace ID starting with T.
    - SLACK_CHANNEL_IDS: Optional. Comma-separated list of channel IDs to limit
    channel access (e.g., "C01234567, C76543210"). If not set, all public
    channels will be listed.
    """

    tool_name: Literal[
        "slack_list_channels",
        "slack_post_message",
        "slack_reply_to_thread",
        "slack_add_reaction",
        "slack_get_channel_history",
        "slack_get_thread_replies",
        "slack_get_users",
        "slack_get_user_profile",
    ]
    """The name of the tool supported by the MCP server."""
    kwargs: dict = {}
    """The keyword arguments to pass to the tool."""
    bot_token: str = "[[slack_bot_token]]"
    """Bot user OAuth token."""
    team_id: str = "[[slack_team_id]]"
    """Slack workspace ID."""
    channel_ids: str | None = None
    """Optional comma separated list of channel IDs."""

    async def run(self, state: State, config: RunnableConfig) -> dict:
        """Run the Slack node."""
        env_vars = {
            "SLACK_BOT_TOKEN": self.bot_token,
            "SLACK_TEAM_ID": self.team_id,
        }
        if self.channel_ids:
            env_vars["SLACK_CHANNEL_IDS"] = self.channel_ids
        transport = NpxStdioTransport(
            "@modelcontextprotocol/server-slack",
            env_vars=env_vars,
        )
        if getattr(transport, "log_file", None) is None:
            log_path = os.getenv("ORCHEO_MCP_STDIO_LOG", "/tmp/orcheo-mcp-stdio.log")
            transport.log_file = Path(log_path)
        async with Client(transport) as client:
            result = await client.call_tool(self.tool_name, self.kwargs)

            return asdict(result)


@registry.register(
    NodeMetadata(
        name="SlackEventsParserNode",
        description="Validate and parse Slack Events API payloads",
        category="slack",
    )
)
class SlackEventsParserNode(TaskNode):
    """Validate Slack signatures and parse Events API payloads."""

    signing_secret: str = "[[slack_signing_secret]]"
    """Slack signing secret."""
    allowed_event_types: list[str] = Field(
        default_factory=lambda: ["app_mention"],
        description="Slack event types allowed to pass through",
    )
    channel_id: str | None = Field(
        default=None,
        description="Optional channel ID to filter events",
    )
    timestamp_tolerance_seconds: int | str = Field(
        default=300,
        description="Maximum age for Slack signature timestamps",
    )
    body_key: str = Field(
        default="body",
        description="Key in inputs that contains the webhook payload",
    )

    @field_validator("timestamp_tolerance_seconds", mode="before")
    @classmethod
    def _validate_timestamp_tolerance(cls, value: Any) -> Any:
        if isinstance(value, str):
            if "{{" in value and "}}" in value:
                return value
            try:
                value = int(value)
            except ValueError as exc:
                msg = "timestamp_tolerance_seconds must be an integer"
                raise ValueError(msg) from exc
        if isinstance(value, int) and value < 0:
            msg = "timestamp_tolerance_seconds must be >= 0"
            raise ValueError(msg)
        return value  # pragma: no cover - defensive code

    def _normalize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return {key.lower(): value for key, value in headers.items()}

    def _extract_inputs(self, state: State) -> dict[str, Any]:
        if isinstance(state, BaseModel):
            state_dict = state.model_dump()
            raw_inputs = state_dict.get("inputs")
            if isinstance(raw_inputs, Mapping):
                return dict(raw_inputs)
            return dict(state_dict)
        if isinstance(state, Mapping):
            state_dict = dict(state)
            raw_inputs = state_dict.get("inputs")
            if isinstance(raw_inputs, Mapping):
                merged = dict(raw_inputs)
                for key in ("body", "headers", "query_params", "source_ip"):
                    if key in state_dict and key not in merged:
                        merged[key] = state_dict[key]
                return merged
            return state_dict
        return {}

    def _extract_raw_body(self, body: Any) -> tuple[str, dict[str, Any]]:
        if isinstance(body, Mapping) and "raw" in body:
            raw_body = body.get("raw")
            if isinstance(raw_body, str):  # pragma: no branch
                return raw_body, self._parse_json(raw_body)
        if isinstance(body, bytes):
            raw_text = body.decode("utf-8", errors="replace")
            return raw_text, self._parse_json(raw_text)
        if isinstance(body, str):
            return body, self._parse_json(body)
        if isinstance(body, Mapping):
            raw_text = json.dumps(body, separators=(",", ":"), ensure_ascii=True)
            return raw_text, dict(body)
        msg = "Slack event payload must be a dict, string, or bytes"
        raise ValueError(msg)

    def _parse_json(self, raw_body: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    def _verify_signature(self, raw_body: str, headers: dict[str, str]) -> None:
        signature = headers.get("x-slack-signature")
        timestamp_value = headers.get("x-slack-request-timestamp")
        if not signature or not timestamp_value:
            raise ValueError("Missing Slack signature headers")

        try:
            timestamp = int(timestamp_value)
        except ValueError as exc:
            raise ValueError("Invalid Slack timestamp header") from exc

        tolerance = self.timestamp_tolerance_seconds
        if isinstance(tolerance, str):
            try:
                tolerance_value = int(tolerance)
            except ValueError as exc:
                msg = "timestamp_tolerance_seconds must resolve to an integer"
                raise ValueError(msg) from exc
        else:
            tolerance_value = tolerance

        if tolerance_value:  # pragma: no branch
            now = int(time.time())
            if abs(now - timestamp) > tolerance_value:
                raise ValueError("Slack request timestamp outside tolerance window")

        signature_base = f"v0:{timestamp}:{raw_body}".encode()
        digest = hmac.new(
            self.signing_secret.encode(),
            signature_base,
            hashlib.sha256,
        ).hexdigest()
        expected = f"v0={digest}"
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Slack signature verification failed")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Parse the Slack Events API payload and validate signatures."""
        inputs = self._extract_inputs(state)
        headers = inputs.get("headers", {})
        if not isinstance(headers, dict):
            msg = "Slack event headers must be a dictionary"
            raise ValueError(msg)

        normalized_headers = self._normalize_headers(headers)
        body = inputs.get(self.body_key)
        raw_body, payload = self._extract_raw_body(body)

        if self.signing_secret:
            if not raw_body:
                raise ValueError("Slack signature verification requires raw payload")
            self._verify_signature(raw_body, normalized_headers)

        # Reject Slack retries to prevent duplicate processing.  Slack sets
        # the x-slack-retry-num header on every retry attempt.
        if normalized_headers.get("x-slack-retry-num") is not None:
            return {
                "is_verification": False,
                "event_type": None,
                "event": None,
                "should_process": False,
            }

        payload_type = payload.get("type")
        if payload_type == "url_verification":
            return {
                "is_verification": True,
                "challenge": payload.get("challenge"),
                "should_process": False,
            }

        if payload_type != "event_callback":
            return {
                "is_verification": False,
                "event_type": payload_type,
                "event": payload.get("event"),
                "should_process": False,
            }

        event = payload.get("event") or {}
        event_type = event.get("type")
        channel = event.get("channel")

        if self.allowed_event_types and event_type not in self.allowed_event_types:
            return {
                "is_verification": False,
                "event_type": event_type,
                "event": event,
                "should_process": False,
            }

        if self.channel_id and channel != self.channel_id:
            return {
                "is_verification": False,
                "event_type": event_type,
                "event": event,
                "should_process": False,
            }

        return {
            "is_verification": False,
            "event_type": event_type,
            "event": event,
            "channel": channel,
            "user": event.get("user"),
            "text": event.get("text"),
            "should_process": True,
        }


__all__ = ["SlackEventsParserNode", "SlackNode"]
