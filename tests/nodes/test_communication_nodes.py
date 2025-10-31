"""Tests for communication nodes."""

from __future__ import annotations
import json
from typing import Any
import httpx
import pytest
import respx
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.communication import DiscordWebhookNode, EmailNode


class DummySMTP:
    """Simple SMTP stub for validating EmailNode behaviour."""

    def __init__(self, host: str, port: int, timeout: float | None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.messages: list[tuple[Any, Any]] = []

    def __enter__(self) -> DummySMTP:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message, to_addrs):  # type: ignore[no-untyped-def]
        self.messages.append((message, to_addrs))
        return {}


@pytest.mark.asyncio
async def test_email_node_sends_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """EmailNode should send a message via SMTP."""

    dummy = DummySMTP("localhost", 1025, timeout=30.0)

    def smtp_factory(host: str, port: int, timeout: float | None) -> DummySMTP:
        assert host == "smtp.test"
        assert port == 2525
        assert timeout == 10.0
        return dummy

    monkeypatch.setattr("orcheo.nodes.communication.smtplib.SMTP", smtp_factory)

    node = EmailNode(
        name="email",
        smtp_host="smtp.test",
        smtp_port=2525,
        timeout=10.0,
        from_address="sender@example.com",
        to_addresses=["recipient@example.com"],
        subject="Test",
        body="Hello",
        username="user",
        password="pass",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["email"]

    assert dummy.started_tls is True
    assert dummy.logged_in == ("user", "pass")
    assert dummy.messages
    assert payload["accepted"] == ["recipient@example.com"]


@pytest.mark.asyncio
async def test_email_node_supports_cc_and_bcc(monkeypatch: pytest.MonkeyPatch) -> None:
    """EmailNode should include CC/BCC recipients and respect TLS settings."""

    dummy = DummySMTP("localhost", 1025, timeout=30.0)

    def smtp_factory(host: str, port: int, timeout: float | None) -> DummySMTP:
        return dummy

    monkeypatch.setattr("orcheo.nodes.communication.smtplib.SMTP", smtp_factory)

    node = EmailNode(
        name="email",
        smtp_host="smtp.test",
        smtp_port=2525,
        from_address="sender@example.com",
        to_addresses=[],
        cc_addresses=["cc@example.com"],
        bcc_addresses=["bcc@example.com"],
        subject="Test",
        body="Hello",
        use_tls=False,
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["email"]

    assert dummy.started_tls is False
    assert dummy.logged_in is None
    assert dummy.messages
    message, recipients = dummy.messages[0]
    assert message["Cc"] == "cc@example.com"
    assert set(recipients) == {"cc@example.com", "bcc@example.com"}
    assert payload["accepted"] == ["cc@example.com", "bcc@example.com"]


@pytest.mark.asyncio
async def test_email_node_requires_recipients() -> None:
    """EmailNode should validate recipients are provided."""

    node = EmailNode(
        name="email",
        smtp_host="smtp.test",
        smtp_port=2525,
        from_address="sender@example.com",
    )

    state = State({"results": {}})
    with pytest.raises(ValueError):
        await node(state, RunnableConfig())


@pytest.mark.asyncio
async def test_discord_webhook_node_posts_payload() -> None:
    """DiscordWebhookNode should post to the configured webhook URL."""

    state = State({"results": {}})
    node = DiscordWebhookNode(
        name="discord",
        webhook_url="https://discordapp.com/api/webhooks/123",
        content="Hello",
        username="Orcheo",
    )

    with respx.mock(base_url="https://discordapp.com") as router:
        route = router.post("/api/webhooks/123").mock(return_value=httpx.Response(204))
        payload = (await node(state, RunnableConfig()))["results"]["discord"]

    assert route.called
    assert payload["status_code"] == 204


@pytest.mark.asyncio
async def test_discord_webhook_node_supports_optional_fields() -> None:
    """DiscordWebhookNode should include optional payload fields when provided."""

    state = State({"results": {}})
    node = DiscordWebhookNode(
        name="discord",
        webhook_url="https://discordapp.com/api/webhooks/456",
        content="Hello",
        username="Orcheo",
        avatar_url="https://example.com/avatar.png",
        embeds=[{"title": "Update"}],
        tts=True,
    )

    with respx.mock(base_url="https://discordapp.com") as router:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(204)

        route = router.post("/api/webhooks/456").mock(side_effect=handler)
        await node(state, RunnableConfig())

    assert route.called
    assert captured["username"] == "Orcheo"
    assert captured["avatar_url"].endswith("avatar.png")
    assert captured["embeds"] == [{"title": "Update"}]
    assert captured["tts"] is True


@pytest.mark.asyncio
async def test_discord_webhook_node_omits_optional_fields_when_none() -> None:
    """DiscordWebhookNode should omit optional fields when they are None."""

    state = State({"results": {}})
    node = DiscordWebhookNode(
        name="discord",
        webhook_url="https://discordapp.com/api/webhooks/789",
        content=None,
        username=None,
        avatar_url=None,
        embeds=None,
        tts=False,
    )

    with respx.mock(base_url="https://discordapp.com") as router:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(204)

        route = router.post("/api/webhooks/789").mock(side_effect=handler)
        await node(state, RunnableConfig())

    assert route.called
    assert "content" not in captured
    assert "username" not in captured
    assert "avatar_url" not in captured
    assert "embeds" not in captured
    assert captured["tts"] is False
