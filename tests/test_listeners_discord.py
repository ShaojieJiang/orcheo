"""Tests for Discord listener normalization and Gateway handling."""

from __future__ import annotations
import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
import pytest
from orcheo.listeners import (
    DiscordGatewayAdapter,
    DiscordGatewayInfo,
    DiscordGatewaySessionStartLimit,
    ListenerCursor,
    ListenerDispatchPayload,
    ListenerPlatform,
    ListenerSubscription,
    discord_intents_bitmask,
    normalize_discord_event,
)
from orcheo_backend.app.repository import InMemoryWorkflowRepository


class FakeDiscordGatewayClient:
    """Simple stub for Discord ``GET /gateway/bot`` responses."""

    def __init__(self, info: DiscordGatewayInfo) -> None:
        self.info = info
        self.calls: list[str] = []

    async def get_gateway_bot(self, *, token: str) -> DiscordGatewayInfo:
        self.calls.append(token)
        return self.info


class FakeDiscordWebSocket:
    """Predictable WebSocket stub for Discord gateway tests."""

    def __init__(self, incoming: list[dict[str, Any]]) -> None:
        self._incoming = [json.dumps(item) for item in incoming]
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        if self._incoming:
            return self._incoming.pop(0)
        await asyncio.sleep(0.01)
        return json.dumps({"op": 7, "d": None})

    async def close(self, code: int = 1000) -> None:
        del code
        self.closed = True


class FakeDiscordConnector:
    """Connector returning a prebuilt fake WebSocket."""

    def __init__(self, websocket: FakeDiscordWebSocket) -> None:
        self.websocket = websocket
        self.calls: list[str] = []

    def connect(self, url: str) -> AbstractAsyncContextManager[FakeDiscordWebSocket]:
        self.calls.append(url)

        @asynccontextmanager
        async def _manager() -> AsyncIterator[FakeDiscordWebSocket]:
            yield self.websocket

        return _manager()


def _listener_graph(*listeners: dict[str, object]) -> dict[str, object]:
    return {"nodes": [], "edges": [], "index": {"listeners": list(listeners)}}


async def _create_discord_subscription(
    *,
    repository: InMemoryWorkflowRepository,
    token: str = "[[discord_bot_token]]",
    intents: list[str] | None = None,
    allowed_guild_ids: list[str] | None = None,
    allowed_channel_ids: list[str] | None = None,
    include_direct_messages: bool = True,
    allowed_message_types: list[str] | None = None,
    require_bot_mention: bool = False,
) -> ListenerSubscription:
    workflow = await repository.create_workflow(
        name="Discord Flow",
        slug=None,
        description=None,
        tags=None,
        actor="author",
    )
    await repository.create_version(
        workflow.id,
        graph=_listener_graph(
            {
                "node_name": "discord_listener",
                "platform": "discord",
                "token": token,
                "intents": intents
                or [
                    "guilds",
                    "guild_messages",
                    "direct_messages",
                    "message_content",
                ],
                "allowed_guild_ids": allowed_guild_ids or [],
                "allowed_channel_ids": allowed_channel_ids or [],
                "include_direct_messages": include_direct_messages,
                "allowed_message_types": allowed_message_types or ["DEFAULT"],
                "require_bot_mention": require_bot_mention,
            }
        ),
        metadata={},
        notes=None,
        created_by="author",
    )
    return (await repository.list_listener_subscriptions(workflow_id=workflow.id))[0]


@pytest.mark.asyncio
async def test_normalize_discord_event_filters_and_routes_message() -> None:
    repository = InMemoryWorkflowRepository()
    subscription = await _create_discord_subscription(
        repository=repository,
        allowed_guild_ids=["guild-1"],
        allowed_channel_ids=["channel-1"],
        require_bot_mention=True,
    )

    payload = normalize_discord_event(
        subscription,
        "MESSAGE_CREATE",
        {
            "id": "message-1",
            "channel_id": "channel-1",
            "guild_id": "guild-1",
            "type": 0,
            "content": "hello discord",
            "author": {"id": "user-1", "username": "Alice"},
            "mentions": [{"id": "bot-1", "bot": True}],
        },
        bot_user_id="bot-1",
    )

    assert isinstance(payload, ListenerDispatchPayload)
    assert payload.message.channel_id == "channel-1"
    assert payload.message.guild_id == "guild-1"
    assert payload.message.text == "hello discord"
    assert payload.reply_target == {
        "channel_id": "channel-1",
        "reply_to_message_id": "message-1",
    }


@pytest.mark.asyncio
async def test_normalize_discord_event_tracks_missing_message_content() -> None:
    repository = InMemoryWorkflowRepository()
    subscription = await _create_discord_subscription(
        repository=repository,
        intents=["guilds", "guild_messages"],
    )

    payload = normalize_discord_event(
        subscription,
        "MESSAGE_CREATE",
        {
            "id": "message-1",
            "channel_id": "channel-1",
            "guild_id": "guild-1",
            "type": 0,
            "content": "",
            "author": {"id": "user-1", "username": "Alice"},
            "mentions": [],
        },
    )

    assert isinstance(payload, ListenerDispatchPayload)
    assert payload.message.text is None
    assert payload.metadata["content_available"] is False


@pytest.mark.asyncio
async def test_normalize_discord_event_ignores_self_authored_messages() -> None:
    repository = InMemoryWorkflowRepository()
    subscription = await _create_discord_subscription(repository=repository)

    payload = normalize_discord_event(
        subscription,
        "MESSAGE_CREATE",
        {
            "id": "message-1",
            "channel_id": "channel-1",
            "type": 0,
            "content": "hello discord",
            "author": {"id": "bot-1", "username": "CD Bot", "bot": True},
            "mentions": [],
        },
        bot_user_id="bot-1",
    )

    assert payload is None


@pytest.mark.asyncio
async def test_discord_gateway_adapter_dispatches_and_saves_cursor() -> None:
    repository = InMemoryWorkflowRepository()
    subscription = await _create_discord_subscription(repository=repository)
    client = FakeDiscordGatewayClient(
        DiscordGatewayInfo(
            url="wss://gateway.discord.gg",
            session_start_limit=DiscordGatewaySessionStartLimit(
                remaining=1,
                reset_after=1000,
            ),
        )
    )
    websocket = FakeDiscordWebSocket(
        [
            {"op": 10, "d": {"heartbeat_interval": 100}},
            {
                "op": 0,
                "t": "READY",
                "s": 1,
                "d": {
                    "session_id": "session-1",
                    "resume_gateway_url": "wss://resume.discord.gg",
                    "user": {"id": "bot-1"},
                },
            },
            {
                "op": 0,
                "t": "MESSAGE_CREATE",
                "s": 2,
                "d": {
                    "id": "message-1",
                    "channel_id": "channel-1",
                    "guild_id": "guild-1",
                    "type": 0,
                    "content": "hello discord",
                    "author": {"id": "user-1", "username": "Alice"},
                    "mentions": [{"id": "bot-1", "bot": True}],
                },
            },
            {"op": 7, "d": None},
        ]
    )
    connector = FakeDiscordConnector(websocket)
    adapter = DiscordGatewayAdapter(
        repository=repository,
        subscription=subscription,
        runtime_id="runtime-1",
        gateway_client=client,
        gateway_connector=connector,
    )

    await adapter.run_session_once(
        token="[[discord_bot_token]]",
        stop_event=asyncio.Event(),
    )

    runs = await repository.list_runs_for_workflow(subscription.workflow_id)
    assert len(runs) == 1
    assert websocket.sent[0]["op"] == 2
    cursor = await repository.get_listener_cursor(subscription.id)
    assert cursor is not None
    assert cursor.discord_session_id == "session-1"
    assert cursor.discord_sequence == 2
    assert cursor.discord_resume_gateway_url == (
        "wss://resume.discord.gg?v=10&encoding=json"
    )
    health = adapter.health()
    assert health.platform is ListenerPlatform.DISCORD
    assert health.status == "healthy"


@pytest.mark.asyncio
async def test_discord_gateway_adapter_resumes_existing_session() -> None:
    repository = InMemoryWorkflowRepository()
    subscription = await _create_discord_subscription(repository=repository)
    await repository.save_listener_cursor(
        ListenerCursor(
            subscription_id=subscription.id,
            discord_session_id="session-1",
            discord_sequence=7,
            discord_resume_gateway_url="wss://resume.discord.gg?v=10&encoding=json",
        )
    )
    client = FakeDiscordGatewayClient(
        DiscordGatewayInfo(
            url="wss://gateway.discord.gg",
            session_start_limit=DiscordGatewaySessionStartLimit(
                remaining=1,
                reset_after=1000,
            ),
        )
    )
    websocket = FakeDiscordWebSocket(
        [
            {"op": 10, "d": {"heartbeat_interval": 100}},
            {"op": 0, "t": "RESUMED", "s": 8, "d": {}},
            {"op": 7, "d": None},
        ]
    )
    connector = FakeDiscordConnector(websocket)
    adapter = DiscordGatewayAdapter(
        repository=repository,
        subscription=subscription,
        runtime_id="runtime-1",
        gateway_client=client,
        gateway_connector=connector,
    )

    await adapter.run_session_once(
        token="[[discord_bot_token]]",
        stop_event=asyncio.Event(),
    )

    assert websocket.sent[0] == {
        "op": 6,
        "d": {
            "token": "[[discord_bot_token]]",
            "session_id": "session-1",
            "seq": 7,
        },
    }
    cursor = await repository.get_listener_cursor(subscription.id)
    assert cursor is not None
    assert cursor.discord_sequence == 8


@pytest.mark.asyncio
async def test_discord_gateway_adapter_waits_when_session_limit_exhausted() -> None:
    repository = InMemoryWorkflowRepository()
    subscription = await _create_discord_subscription(repository=repository)
    client = FakeDiscordGatewayClient(
        DiscordGatewayInfo(
            url="wss://gateway.discord.gg",
            session_start_limit=DiscordGatewaySessionStartLimit(
                remaining=0,
                reset_after=10,
            ),
        )
    )
    websocket = FakeDiscordWebSocket([{"op": 10, "d": {"heartbeat_interval": 100}}])
    connector = FakeDiscordConnector(websocket)
    adapter = DiscordGatewayAdapter(
        repository=repository,
        subscription=subscription,
        runtime_id="runtime-1",
        gateway_client=client,
        gateway_connector=connector,
    )

    await adapter.run_session_once(
        token="[[discord_bot_token]]",
        stop_event=asyncio.Event(),
    )

    assert connector.calls == []
    assert adapter.health().status == "backoff"


@pytest.mark.asyncio
async def test_discord_gateway_adapter_heartbeat_uses_latest_sequence() -> None:
    repository = InMemoryWorkflowRepository()
    subscription = await _create_discord_subscription(repository=repository)
    websocket = FakeDiscordWebSocket([])
    adapter = DiscordGatewayAdapter(
        repository=repository,
        subscription=subscription,
        runtime_id="runtime-1",
    )
    adapter._sequence = 42
    stop_event = asyncio.Event()

    task = asyncio.create_task(
        adapter._heartbeat_loop(
            websocket=websocket,
            stop_event=stop_event,
            interval_seconds=0.01,
        )
    )
    await asyncio.sleep(0.03)
    stop_event.set()
    await task

    assert websocket.sent
    assert websocket.sent[0] == {"op": 1, "d": 42}


def test_discord_intents_bitmask_includes_configured_flags() -> None:
    bitmask = discord_intents_bitmask(
        ["guilds", "guild_messages", "direct_messages", "message_content"]
    )
    assert bitmask == (1 | (1 << 9) | (1 << 12) | (1 << 15))
