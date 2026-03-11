"""Discord Gateway adapter for private listener subscriptions."""

from __future__ import annotations
import asyncio
import json
import sys
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any, Literal, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID
import httpx
import websockets
from orcheo.listeners.models import (
    ListenerCursor,
    ListenerDispatchMessage,
    ListenerDispatchPayload,
    ListenerHealthSnapshot,
    ListenerPlatform,
    ListenerSubscription,
)
from orcheo.models.base import OrcheoBaseModel, _utcnow


_DISCORD_INTENT_BITS = {
    "guilds": 1 << 0,
    "guild_messages": 1 << 9,
    "direct_messages": 1 << 12,
    "message_content": 1 << 15,
}

_DISCORD_MESSAGE_TYPES = {
    0: "DEFAULT",
    19: "REPLY",
}


class DiscordGatewaySessionStartLimit(OrcheoBaseModel):
    """Discord session-start rate-limit envelope."""

    total: int | None = None
    remaining: int | None = None
    reset_after: int | None = None
    max_concurrency: int | None = None


class DiscordGatewayInfo(OrcheoBaseModel):
    """Gateway bootstrap payload from ``GET /gateway/bot``."""

    url: str
    session_start_limit: DiscordGatewaySessionStartLimit | None = None


class DiscordListenerRepository(Protocol):
    """Repository operations required by the Discord gateway adapter."""

    async def get_listener_cursor(
        self,
        subscription_id: UUID,
    ) -> ListenerCursor | None:
        """Return the saved Discord resume cursor for the subscription."""

    async def save_listener_cursor(
        self,
        cursor: ListenerCursor,
    ) -> ListenerCursor:
        """Persist the latest Discord resume cursor."""

    async def dispatch_listener_event(
        self,
        subscription_id: UUID,
        payload: ListenerDispatchPayload,
    ) -> object | None:
        """Dispatch a normalized Discord event into the workflow runtime."""


class DiscordGatewayHttpClient(Protocol):
    """HTTP client contract used to fetch Discord gateway information."""

    async def get_gateway_bot(self, *, token: str) -> DiscordGatewayInfo:
        """Return the Discord gateway URL and session-start limits."""


class DiscordGatewayConnection(Protocol):
    """WebSocket connection contract used by the Discord adapter."""

    async def send(self, message: str) -> None:
        """Send a text frame to the Discord Gateway."""

    async def recv(self) -> str | bytes:
        """Receive the next Gateway frame."""

    async def close(self, code: int = 1000) -> None:
        """Close the WebSocket connection."""


class DiscordGatewayConnector(Protocol):
    """Factory for Discord Gateway WebSocket connections."""

    def connect(
        self,
        url: str,
    ) -> AbstractAsyncContextManager[DiscordGatewayConnection]:
        """Open a managed WebSocket connection to the Gateway."""


class DefaultDiscordGatewayHttpClient:
    """HTTPX-backed client for Discord Gateway bootstrap calls."""

    BASE_URL = "https://discord.com/api/v10"

    async def get_gateway_bot(self, *, token: str) -> DiscordGatewayInfo:
        """Fetch the current Gateway URL and session-start limits."""
        async with httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bot {token}"},
            timeout=10.0,
        ) as client:
            response = await client.get("/gateway/bot")
            response.raise_for_status()
            body = response.json()
        if not isinstance(body, Mapping):
            msg = "Discord gateway bootstrap returned an invalid payload"
            raise ValueError(msg)
        url = body.get("url")
        if not isinstance(url, str) or not url:
            msg = "Discord gateway bootstrap did not include a URL"
            raise ValueError(msg)
        limit = body.get("session_start_limit")
        return DiscordGatewayInfo(
            url=_with_gateway_params(url),
            session_start_limit=(
                DiscordGatewaySessionStartLimit.model_validate(limit)
                if isinstance(limit, Mapping)
                else None
            ),
        )


class DefaultDiscordGatewayConnector:
    """Websockets-backed connector for Discord Gateway sessions."""

    def connect(
        self,
        url: str,
    ) -> AbstractAsyncContextManager[DiscordGatewayConnection]:
        """Open a WebSocket connection to the provided Discord Gateway URL."""
        return websockets.connect(url, open_timeout=10.0)


class DiscordGatewayAdapter:
    """Maintain a Discord Gateway session and dispatch message events."""

    def __init__(
        self,
        *,
        repository: DiscordListenerRepository,
        subscription: ListenerSubscription,
        runtime_id: str,
        gateway_client: DiscordGatewayHttpClient | None = None,
        gateway_connector: DiscordGatewayConnector | None = None,
    ) -> None:
        """Create a Discord Gateway adapter for one listener subscription."""
        self._repository = repository
        self.subscription = subscription
        self._runtime_id = runtime_id
        self._gateway_client = gateway_client or DefaultDiscordGatewayHttpClient()
        self._gateway_connector = gateway_connector or DefaultDiscordGatewayConnector()
        self._status: Literal["starting", "healthy", "backoff", "stopped"] = "starting"
        self._last_polled_at: datetime | None = None
        self._last_event_at = subscription.last_event_at
        self._consecutive_failures = 0
        self._detail: str | None = None
        self._sequence: int | None = None
        self._bot_user_id: str | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        """Maintain a healthy Discord Gateway session until asked to stop."""
        token = str(self.subscription.config.get("token", ""))
        while not stop_event.is_set():
            try:
                await self.run_session_once(token=token, stop_event=stop_event)
                self._detail = None
            except Exception as exc:  # pragma: no cover - exercised via tests
                self._consecutive_failures += 1
                self._detail = str(exc)
                self._status = "backoff"
                backoff_min_seconds = float(
                    self.subscription.config.get("backoff_min_seconds", 1.0)
                )
                backoff_max_seconds = float(
                    self.subscription.config.get("backoff_max_seconds", 30.0)
                )
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=min(
                            backoff_max_seconds,
                            max(
                                backoff_min_seconds,
                                backoff_min_seconds * self._consecutive_failures,
                            ),
                        ),
                    )
                except TimeoutError:
                    continue
        self._status = "stopped"

    async def run_session_once(
        self,
        *,
        token: str,
        stop_event: asyncio.Event,
    ) -> None:
        """Run one Discord Gateway connection attempt until reconnect or stop."""
        cursor = await self._repository.get_listener_cursor(self.subscription.id)
        state = cursor or ListenerCursor(subscription_id=self.subscription.id)
        self._sequence = state.discord_sequence

        gateway = await self._gateway_client.get_gateway_bot(token=token)
        limit = gateway.session_start_limit
        if (
            limit is not None
            and limit.remaining is not None
            and limit.remaining <= 0
            and limit.reset_after is not None
        ):
            self._status = "backoff"
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=max(limit.reset_after / 1000, 0.01),
                )
            except TimeoutError:
                pass
            return

        gateway_url = state.discord_resume_gateway_url or gateway.url
        async with self._gateway_connector.connect(gateway_url) as websocket:
            hello = await self._receive_gateway_payload(websocket)
            interval_seconds = _extract_heartbeat_interval(hello)
            heartbeat_stop = asyncio.Event()
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(
                    websocket=websocket,
                    stop_event=heartbeat_stop,
                    interval_seconds=interval_seconds,
                )
            )
            try:
                await self._send_start_session(
                    websocket=websocket,
                    token=token,
                    cursor=state,
                )
                self._status = "healthy"
                self._consecutive_failures = 0
                while not stop_event.is_set():
                    try:
                        frame = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    except TimeoutError:
                        continue
                    should_reconnect = await self._handle_gateway_frame(
                        websocket=websocket,
                        frame=frame,
                        cursor=state,
                    )
                    if should_reconnect:
                        return
            finally:
                heartbeat_stop.set()
                await heartbeat_task
                await websocket.close()

    def health(self) -> ListenerHealthSnapshot:
        """Return the current adapter health snapshot."""
        return ListenerHealthSnapshot(
            subscription_id=self.subscription.id,
            runtime_id=self._runtime_id,
            status=self._status,
            platform=ListenerPlatform.DISCORD,
            last_polled_at=self._last_polled_at,
            last_event_at=self._last_event_at,
            consecutive_failures=self._consecutive_failures,
            detail=self._detail,
        )

    async def _heartbeat_loop(
        self,
        *,
        websocket: DiscordGatewayConnection,
        stop_event: asyncio.Event,
        interval_seconds: float,
    ) -> None:
        """Send periodic Discord Gateway heartbeats."""
        interval = max(interval_seconds, 0.01)
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except TimeoutError:
                await self._send_gateway_payload(
                    websocket,
                    {"op": 1, "d": self._sequence},
                )

    async def _send_start_session(
        self,
        *,
        websocket: DiscordGatewayConnection,
        token: str,
        cursor: ListenerCursor,
    ) -> None:
        """Send either IDENTIFY or RESUME for the Discord Gateway session."""
        if (
            cursor.discord_session_id is not None
            and cursor.discord_sequence is not None
            and cursor.discord_resume_gateway_url
        ):
            await self._send_gateway_payload(
                websocket,
                {
                    "op": 6,
                    "d": {
                        "token": token,
                        "session_id": cursor.discord_session_id,
                        "seq": cursor.discord_sequence,
                    },
                },
            )
            return

        await self._send_gateway_payload(
            websocket,
            {
                "op": 2,
                "d": {
                    "token": token,
                    "intents": discord_intents_bitmask(
                        list(self.subscription.config.get("intents", []))
                    ),
                    "properties": {
                        "os": sys.platform,
                        "browser": "orcheo",
                        "device": "orcheo",
                    },
                },
            },
        )

    async def _handle_gateway_frame(
        self,
        *,
        websocket: DiscordGatewayConnection,
        frame: str | bytes,
        cursor: ListenerCursor,
    ) -> bool:
        """Process one Discord Gateway frame and return reconnect intent."""
        payload = _decode_gateway_payload(frame)
        self._last_polled_at = _utcnow()

        sequence = payload.get("s")
        if isinstance(sequence, int):
            self._sequence = sequence
            cursor.discord_sequence = sequence

        op = payload.get("op")
        if op != 0:
            return await self._handle_non_dispatch_op(
                websocket=websocket,
                cursor=cursor,
                op=op,
            )

        event_type = payload.get("t")
        data = payload.get("d", {})
        if not isinstance(event_type, str) or not isinstance(data, Mapping):
            return False

        return await self._handle_dispatch_event(
            event_type=event_type,
            data=data,
            cursor=cursor,
        )

    async def _handle_non_dispatch_op(
        self,
        *,
        websocket: DiscordGatewayConnection,
        cursor: ListenerCursor,
        op: object,
    ) -> bool:
        """Handle non-dispatch Discord Gateway opcodes."""
        if op == 11:
            return False
        if op == 1:
            await self._send_gateway_payload(
                websocket,
                {"op": 1, "d": self._sequence},
            )
            return False
        if op == 7:
            self._detail = "gateway_requested_reconnect"
            return True
        if op != 9:
            return False

        cursor.discord_session_id = None
        cursor.discord_sequence = None
        cursor.discord_resume_gateway_url = None
        await self._repository.save_listener_cursor(cursor)
        self._bot_user_id = None
        return True

    async def _handle_dispatch_event(
        self,
        *,
        event_type: str,
        data: Mapping[str, Any],
        cursor: ListenerCursor,
    ) -> bool:
        """Handle Discord dispatch events and persist cursor state."""
        if event_type == "READY":
            await self._handle_ready_event(data=data, cursor=cursor)
            return False

        if event_type == "RESUMED":
            await self._repository.save_listener_cursor(cursor)
            return False

        normalized = normalize_discord_event(
            self.subscription,
            event_type,
            data,
            bot_user_id=self._bot_user_id,
        )
        if normalized is not None:
            await self._repository.dispatch_listener_event(
                self.subscription.id,
                normalized,
            )
            self._last_event_at = _utcnow()
        await self._repository.save_listener_cursor(cursor)
        return False

    async def _handle_ready_event(
        self,
        *,
        data: Mapping[str, Any],
        cursor: ListenerCursor,
    ) -> None:
        """Persist Discord READY event session state."""
        session_id = data.get("session_id")
        if isinstance(session_id, str):
            cursor.discord_session_id = session_id
        resume_url = data.get("resume_gateway_url")
        if isinstance(resume_url, str) and resume_url:
            cursor.discord_resume_gateway_url = _with_gateway_params(resume_url)
        user = data.get("user")
        if isinstance(user, Mapping):
            user_id = user.get("id")
            if user_id is not None:
                self._bot_user_id = str(user_id)
        await self._repository.save_listener_cursor(cursor)

    async def _receive_gateway_payload(
        self,
        websocket: DiscordGatewayConnection,
    ) -> dict[str, Any]:
        """Receive and decode a Discord Gateway frame."""
        return _decode_gateway_payload(await websocket.recv())

    async def _send_gateway_payload(
        self,
        websocket: DiscordGatewayConnection,
        payload: dict[str, Any],
    ) -> None:
        """Serialize and send a Discord Gateway frame."""
        self._last_polled_at = _utcnow()
        await websocket.send(json.dumps(payload))


def discord_intents_bitmask(intents: list[str]) -> int:
    """Convert configured Discord intent names into a Gateway bitmask."""
    bitmask = 0
    for item in intents:
        bitmask |= _DISCORD_INTENT_BITS.get(str(item).strip().lower(), 0)
    return bitmask


def normalize_discord_event(
    subscription: ListenerSubscription,
    event_type: str,
    event: Mapping[str, Any],
    *,
    bot_user_id: str | None = None,
) -> ListenerDispatchPayload | None:
    """Normalize a Discord dispatch event into the shared listener payload."""
    if event_type != "MESSAGE_CREATE":
        return None

    guild_id = _string_or_none(event.get("guild_id"))
    channel_id = _string_or_none(event.get("channel_id"))
    message_id = _string_or_none(event.get("id"))
    if channel_id is None or message_id is None:
        return None

    message_type_name = _discord_message_type_name(event.get("type"))
    if not _discord_message_passes_filters(
        subscription=subscription,
        guild_id=guild_id,
        channel_id=channel_id,
        message_type_name=message_type_name,
        mentions=event.get("mentions"),
        bot_user_id=bot_user_id,
    ):
        return None

    author = event.get("author", {})
    if not isinstance(author, Mapping):
        author = {}
    if _is_self_authored_message(author, bot_user_id=bot_user_id):
        return None
    content_available = True
    content = event.get("content")
    if not isinstance(content, str):
        content = None
    if not _has_message_content_intent(subscription):
        if content in {None, ""}:
            content_available = False
        content = content or None

    return _build_discord_dispatch_payload(
        subscription=subscription,
        event_type=event_type,
        guild_id=guild_id,
        channel_id=channel_id,
        message_id=message_id,
        message_type_name=message_type_name,
        author=author,
        content=content,
        content_available=content_available,
        event=event,
    )


def _discord_message_passes_filters(
    *,
    subscription: ListenerSubscription,
    guild_id: str | None,
    channel_id: str,
    message_type_name: str | None,
    mentions: object,
    bot_user_id: str | None,
) -> bool:
    """Return whether a Discord message passes configured listener filters."""
    if guild_id is None and not bool(
        subscription.config.get("include_direct_messages", True)
    ):
        return False

    allowed_guild_ids = {
        str(value)
        for value in subscription.config.get("allowed_guild_ids", [])
        if str(value).strip()
    }
    if allowed_guild_ids and guild_id not in allowed_guild_ids:
        return False

    allowed_channel_ids = {
        str(value)
        for value in subscription.config.get("allowed_channel_ids", [])
        if str(value).strip()
    }
    if allowed_channel_ids and channel_id not in allowed_channel_ids:
        return False

    allowed_message_types = {
        str(value).strip().upper()
        for value in subscription.config.get("allowed_message_types", [])
        if str(value).strip()
    }
    if (
        allowed_message_types
        and message_type_name is not None
        and message_type_name not in allowed_message_types
    ):
        return False

    if bool(subscription.config.get("require_bot_mention", False)):
        return _mentions_bot(mentions, bot_user_id=bot_user_id)
    return True


def _build_discord_dispatch_payload(
    *,
    subscription: ListenerSubscription,
    event_type: str,
    guild_id: str | None,
    channel_id: str,
    message_id: str,
    message_type_name: str | None,
    author: Mapping[str, Any],
    content: str | None,
    content_available: bool,
    event: Mapping[str, Any],
) -> ListenerDispatchPayload:
    """Build the normalized dispatch payload for a Discord message event."""
    return ListenerDispatchPayload(
        platform=ListenerPlatform.DISCORD,
        event_type=event_type,
        dedupe_key=f"discord:message:{message_id}",
        bot_identity=subscription.bot_identity_key,
        message=ListenerDispatchMessage(
            chat_id=channel_id,
            channel_id=channel_id,
            guild_id=guild_id,
            message_id=message_id,
            user_id=_string_or_none(author.get("id")),
            username=_string_or_none(author.get("username")),
            text=content,
            chat_type="dm" if guild_id is None else "guild",
            metadata={
                "message_type": message_type_name,
                "content_available": content_available,
            },
        ),
        reply_target={
            "channel_id": channel_id,
            "reply_to_message_id": message_id,
        },
        raw_event=dict(event),
        metadata={
            "node_name": subscription.node_name,
            "message_type": message_type_name,
            "content_available": content_available,
        },
    )


def _decode_gateway_payload(frame: str | bytes) -> dict[str, Any]:
    """Deserialize a Discord Gateway frame into a mapping payload."""
    if isinstance(frame, bytes):
        frame = frame.decode("utf-8")
    payload = json.loads(frame)
    if not isinstance(payload, dict):
        msg = "Discord Gateway frame was not a JSON object"
        raise ValueError(msg)
    return payload


def _extract_heartbeat_interval(payload: Mapping[str, Any]) -> float:
    """Return the heartbeat interval from a Discord HELLO payload."""
    if payload.get("op") != 10:
        msg = "Discord Gateway did not start with HELLO"
        raise ValueError(msg)
    data = payload.get("d", {})
    if not isinstance(data, Mapping):
        msg = "Discord HELLO payload did not include a heartbeat interval"
        raise ValueError(msg)
    heartbeat_interval = data.get("heartbeat_interval")
    if not isinstance(heartbeat_interval, int | float):
        msg = "Discord heartbeat interval was missing or invalid"
        raise ValueError(msg)
    return max(float(heartbeat_interval) / 1000, 0.01)


def _discord_message_type_name(value: object) -> str | None:
    """Return the human-readable Discord message type name."""
    if isinstance(value, str) and value.strip():
        return value.strip().upper()
    if isinstance(value, int):
        return _DISCORD_MESSAGE_TYPES.get(value, str(value))
    return None


def _has_message_content_intent(subscription: ListenerSubscription) -> bool:
    """Return whether the listener subscription requested message content."""
    return "message_content" in {
        str(intent).strip().lower() for intent in subscription.config.get("intents", [])
    }


def _mentions_bot(mentions: object, *, bot_user_id: str | None) -> bool:
    """Return whether the Discord message mentions the configured bot."""
    if bot_user_id is None:
        return False
    if not isinstance(mentions, list):
        return False
    for mention in mentions:
        if not isinstance(mention, Mapping):
            continue
        mention_id = _string_or_none(mention.get("id"))
        if mention_id == bot_user_id:
            return True
    return False


def _is_self_authored_message(
    author: Mapping[str, Any],
    *,
    bot_user_id: str | None,
) -> bool:
    """Return whether the event author matches the connected Discord bot."""
    if bot_user_id is None:
        return False
    return _string_or_none(author.get("id")) == bot_user_id


def _string_or_none(value: object) -> str | None:
    """Return a string value or ``None`` if the value is missing."""
    if value is None:
        return None
    return str(value)


def _with_gateway_params(url: str) -> str:
    """Ensure the Gateway URL includes the expected version and encoding."""
    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.setdefault("v", "10")
    query.setdefault("encoding", "json")
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(query), split.fragment)
    )


__all__ = [
    "DefaultDiscordGatewayConnector",
    "DefaultDiscordGatewayHttpClient",
    "DiscordGatewayAdapter",
    "DiscordGatewayConnection",
    "DiscordGatewayConnector",
    "DiscordGatewayHttpClient",
    "DiscordGatewayInfo",
    "DiscordGatewaySessionStartLimit",
    "discord_intents_bitmask",
    "normalize_discord_event",
]
