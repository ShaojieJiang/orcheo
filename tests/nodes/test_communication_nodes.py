from __future__ import annotations

import httpx
import pytest

from orcheo.graph.state import State
from orcheo.nodes.communication import DiscordEmbed, DiscordMessage, EmailNotification


@pytest.mark.asyncio()
async def test_email_notification_payload() -> None:
    node = EmailNotification(
        name="email",
        to=["ops@example.com"],
        subject="Alert",
        body="Workflow completed",
        from_address="noreply@example.com",
    )
    state = State({"results": {}})
    output = await node(state, None)
    assert output["results"]["email"]["subject"] == "Alert"


@pytest.mark.asyncio()
async def test_discord_message_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, httpx.Request] = {}

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            self._client = httpx.AsyncClient()

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, *exc_info) -> None:
            await self._client.aclose()

        async def post(self, url: str, json: dict[str, object]) -> httpx.Response:
            request = httpx.Request("POST", url, json=json)
            captured["request"] = request
            return httpx.Response(204)

    monkeypatch.setattr(
        "orcheo.nodes.communication.httpx.AsyncClient", DummyAsyncClient
    )

    node = DiscordMessage(
        name="discord",
        webhook_url="https://hooks.example.com/discord",
        content="Hello",
        embeds=[DiscordEmbed(title="Run", description="completed")],
        send=True,
    )
    state = State({"results": {}})
    output = await node(state, None)
    assert output["results"]["discord"]["content"] == "Hello"
    assert "request" in captured
