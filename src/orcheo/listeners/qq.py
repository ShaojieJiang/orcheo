"""QQ Gateway adapter and token helpers for private listener subscriptions."""

from __future__ import annotations
import asyncio
import json
import sys
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol
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


_QQ_EVENT_INTENT_BITS = {
    "MESSAGE_CREATE": 1 << 9,
    "DIRECT_MESSAGE_CREATE": 1 << 12,
    "C2C_MESSAGE_CREATE": 1 << 25,
    "GROUP_AT_MESSAGE_CREATE": 1 << 25,
    "AT_MESSAGE_CREATE": 1 << 30,
}


class QQAccessTokenPayload(OrcheoBaseModel):
    """Access-token response from Tencent's auth endpoint."""

    access_token: str
    expires_in: int


class QQGatewaySessionStartLimit(OrcheoBaseModel):
    """QQ session-start rate-limit envelope."""

    total: int | None = None
    remaining: int | None = None
    reset_after: int | None = None
    max_concurrency: int | None = None


class QQGatewayInfo(OrcheoBaseModel):
    """Gateway bootstrap payload from ``GET /gateway/bot``."""

    url: str
    shards: int | None = None
    session_start_limit: QQGatewaySessionStartLimit | None = None


class QQListenerRepository(Protocol):
    """Repository operations required by the QQ Gateway adapter."""

    async def get_listener_cursor(
        self,
        subscription_id: UUID,
    ) -> ListenerCursor | None:
        """Return the saved QQ resume cursor for the subscription."""

    async def save_listener_cursor(
        self,
        cursor: ListenerCursor,
    ) -> ListenerCursor:
        """Persist the latest QQ resume cursor."""

    async def dispatch_listener_event(
        self,
        subscription_id: UUID,
        payload: ListenerDispatchPayload,
    ) -> object | None:
        """Dispatch a normalized QQ event into the workflow runtime."""


class QQAccessTokenHttpClient(Protocol):
    """HTTP client contract used to fetch QQ access tokens."""

    async def fetch_access_token(
        self,
        *,
        app_id: str,
        client_secret: str,
    ) -> QQAccessTokenPayload:
        """Return an access token for the provided QQ app credentials."""


class QQAccessTokenProvider(Protocol):
    """Contract for QQ access-token retrieval and caching."""

    async def get_access_token(
        self,
        *,
        app_id: str,
        client_secret: str,
    ) -> str:
        """Return a valid QQ access token for the app."""


class QQGatewayHttpClient(Protocol):
    """HTTP client contract used to fetch QQ gateway information."""

    async def get_gateway_bot(
        self,
        *,
        app_id: str,
        client_secret: str,
        sandbox: bool = False,
    ) -> QQGatewayInfo:
        """Return the QQ gateway URL and session-start limits."""


class QQGatewayConnection(Protocol):
    """WebSocket connection contract used by the QQ adapter."""

    async def send(self, message: str) -> None:
        """Send a text frame to the QQ Gateway."""

    async def recv(self) -> str | bytes:
        """Receive the next Gateway frame."""

    async def close(self, code: int = 1000) -> None:
        """Close the WebSocket connection."""


class QQGatewayConnector(Protocol):
    """Factory for QQ Gateway WebSocket connections."""

    def connect(
        self,
        url: str,
    ) -> AbstractAsyncContextManager[QQGatewayConnection]:
        """Open a managed WebSocket connection to the Gateway."""


class DefaultQQAccessTokenHttpClient:
    """HTTPX-backed client for QQ access-token retrieval."""

    TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"

    async def fetch_access_token(
        self,
        *,
        app_id: str,
        client_secret: str,
    ) -> QQAccessTokenPayload:
        """Fetch an access token for one QQ app."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                self.TOKEN_URL,
                json={"appId": app_id, "clientSecret": client_secret},
            )
            response.raise_for_status()
            body = response.json()
        if not isinstance(body, Mapping):
            msg = "QQ access-token endpoint returned an invalid payload"
            raise ValueError(msg)
        token = body.get("access_token")
        expires_in = body.get("expires_in")
        if not isinstance(token, str) or not token:
            msg = "QQ access-token payload did not include access_token"
            raise ValueError(msg)
        if isinstance(expires_in, str):
            expires_in = int(expires_in)
        if not isinstance(expires_in, int):
            msg = "QQ access-token payload did not include expires_in"
            raise ValueError(msg)
        return QQAccessTokenPayload(
            access_token=token,
            expires_in=expires_in,
        )


class DefaultQQAccessTokenProvider:
    """Shared per-AppID access-token cache for QQ listeners and send nodes."""

    _cache: dict[str, tuple[str, datetime]] = {}
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        http_client: QQAccessTokenHttpClient | None = None,
        *,
        refresh_overlap_seconds: int = 60,
    ) -> None:
        """Create a token provider with the documented overlap window."""
        self._http_client = http_client or DefaultQQAccessTokenHttpClient()
        self._refresh_overlap_seconds = refresh_overlap_seconds

    async def get_access_token(
        self,
        *,
        app_id: str,
        client_secret: str,
    ) -> str:
        """Return a cached or freshly fetched QQ access token."""
        cached = self._cache.get(app_id)
        now = _utcnow()
        if cached is not None and now < cached[1] - timedelta(
            seconds=self._refresh_overlap_seconds
        ):
            return cached[0]

        lock = self._locks.setdefault(app_id, asyncio.Lock())
        async with lock:
            cached = self._cache.get(app_id)
            now = _utcnow()
            if cached is not None and now < cached[1] - timedelta(
                seconds=self._refresh_overlap_seconds
            ):
                return cached[0]
            payload = await self._http_client.fetch_access_token(
                app_id=app_id,
                client_secret=client_secret,
            )
            expires_at = now + timedelta(seconds=payload.expires_in)
            self._cache[app_id] = (payload.access_token, expires_at)
            return payload.access_token


class DefaultQQGatewayHttpClient:
    """HTTPX-backed client for QQ gateway bootstrap calls."""

    def __init__(
        self,
        *,
        token_provider: QQAccessTokenProvider | None = None,
    ) -> None:
        """Create a QQ gateway bootstrap client."""
        self._token_provider = token_provider or DefaultQQAccessTokenProvider()

    async def get_gateway_bot(
        self,
        *,
        app_id: str,
        client_secret: str,
        sandbox: bool = False,
    ) -> QQGatewayInfo:
        """Fetch the current gateway URL and session-start limits."""
        token = await self._token_provider.get_access_token(
            app_id=app_id,
            client_secret=client_secret,
        )
        base_url = (
            "https://sandbox.api.sgroup.qq.com"
            if sandbox
            else "https://api.sgroup.qq.com"
        )
        async with httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"QQBot {token}"},
            timeout=10.0,
        ) as client:
            response = await client.get("/gateway/bot")
            response.raise_for_status()
            body = response.json()
        if not isinstance(body, Mapping):
            msg = "QQ gateway bootstrap returned an invalid payload"
            raise ValueError(msg)
        url = body.get("url")
        if not isinstance(url, str) or not url:
            msg = "QQ gateway bootstrap did not include a URL"
            raise ValueError(msg)
        limit = body.get("session_start_limit")
        shards = body.get("shards")
        return QQGatewayInfo(
            url=url,
            shards=shards if isinstance(shards, int) else None,
            session_start_limit=(
                QQGatewaySessionStartLimit.model_validate(limit)
                if isinstance(limit, Mapping)
                else None
            ),
        )


class DefaultQQGatewayConnector:
    """Websockets-backed connector for QQ Gateway sessions."""

    def connect(
        self,
        url: str,
    ) -> AbstractAsyncContextManager[QQGatewayConnection]:
        """Open a WebSocket connection to the provided QQ Gateway URL."""
        return websockets.connect(url, open_timeout=10.0)


class QQGatewayAdapter:
    """Maintain a QQ Gateway session and dispatch message events."""

    def __init__(
        self,
        *,
        repository: QQListenerRepository,
        subscription: ListenerSubscription,
        runtime_id: str,
        token_provider: QQAccessTokenProvider | None = None,
        gateway_client: QQGatewayHttpClient | None = None,
        gateway_connector: QQGatewayConnector | None = None,
    ) -> None:
        """Create a QQ Gateway adapter for one listener subscription."""
        self._repository = repository
        self.subscription = subscription
        self._runtime_id = runtime_id
        self._token_provider = token_provider or DefaultQQAccessTokenProvider()
        self._gateway_client = gateway_client or DefaultQQGatewayHttpClient(
            token_provider=self._token_provider
        )
        self._gateway_connector = gateway_connector or DefaultQQGatewayConnector()
        self._status: Literal["starting", "healthy", "backoff", "stopped"] = "starting"
        self._last_polled_at: datetime | None = None
        self._last_event_at = subscription.last_event_at
        self._consecutive_failures = 0
        self._detail: str | None = None
        self._sequence: int | None = None
        self._bot_user_id: str | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        """Maintain a healthy QQ Gateway session until asked to stop."""
        app_id = str(self.subscription.config.get("app_id", ""))
        client_secret = str(self.subscription.config.get("client_secret", ""))
        sandbox = bool(self.subscription.config.get("sandbox", False))
        while not stop_event.is_set():
            try:
                await self.run_session_once(
                    app_id=app_id,
                    client_secret=client_secret,
                    sandbox=sandbox,
                    stop_event=stop_event,
                )
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
        app_id: str,
        client_secret: str,
        sandbox: bool,
        stop_event: asyncio.Event,
    ) -> None:
        """Run one QQ Gateway connection attempt until reconnect or stop."""
        cursor = await self._repository.get_listener_cursor(self.subscription.id)
        state = cursor or ListenerCursor(subscription_id=self.subscription.id)
        self._sequence = state.qq_sequence

        gateway = await self._gateway_client.get_gateway_bot(
            app_id=app_id,
            client_secret=client_secret,
            sandbox=sandbox,
        )
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

        token = await self._token_provider.get_access_token(
            app_id=app_id,
            client_secret=client_secret,
        )
        gateway_url = state.qq_resume_gateway_url or gateway.url
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
                    token=f"QQBot {token}",
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
                        gateway_url=gateway.url,
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
            platform=ListenerPlatform.QQ,
            last_polled_at=self._last_polled_at,
            last_event_at=self._last_event_at,
            consecutive_failures=self._consecutive_failures,
            detail=self._detail,
        )

    async def _heartbeat_loop(
        self,
        *,
        websocket: QQGatewayConnection,
        stop_event: asyncio.Event,
        interval_seconds: float,
    ) -> None:
        """Send periodic QQ Gateway heartbeats."""
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
        websocket: QQGatewayConnection,
        token: str,
        cursor: ListenerCursor,
    ) -> None:
        """Send either IDENTIFY or RESUME for the QQ Gateway session."""
        if cursor.qq_session_id is not None and cursor.qq_sequence is not None:
            await self._send_gateway_payload(
                websocket,
                {
                    "op": 6,
                    "d": {
                        "token": token,
                        "session_id": cursor.qq_session_id,
                        "seq": cursor.qq_sequence,
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
                    "intents": qq_intents_bitmask(
                        list(self.subscription.config.get("allowed_events", []))
                    ),
                    "properties": {
                        "$os": sys.platform,
                        "$browser": "orcheo",
                        "$device": "orcheo",
                    },
                },
            },
        )

    async def _handle_gateway_frame(
        self,
        *,
        websocket: QQGatewayConnection,
        frame: str | bytes,
        cursor: ListenerCursor,
        gateway_url: str,
    ) -> bool:
        """Process one QQ Gateway frame and return reconnect intent."""
        payload = _decode_gateway_payload(frame)
        self._last_polled_at = _utcnow()

        sequence = payload.get("s")
        if isinstance(sequence, int):
            self._sequence = sequence
            cursor.qq_sequence = sequence

        op = payload.get("op")
        if op != 0:
            return await self._handle_non_dispatch_op(
                websocket=websocket,
                cursor=cursor,
                gateway_url=gateway_url,
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
            gateway_url=gateway_url,
        )

    async def _handle_non_dispatch_op(
        self,
        *,
        websocket: QQGatewayConnection,
        cursor: ListenerCursor,
        gateway_url: str,
        op: object,
    ) -> bool:
        """Handle non-dispatch QQ Gateway opcodes."""
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
            cursor.qq_resume_gateway_url = gateway_url
            await self._repository.save_listener_cursor(cursor)
            return True
        if op != 9:
            return False

        cursor.qq_session_id = None
        cursor.qq_sequence = None
        cursor.qq_resume_gateway_url = None
        await self._repository.save_listener_cursor(cursor)
        self._bot_user_id = None
        return True

    async def _handle_dispatch_event(
        self,
        *,
        event_type: str,
        data: Mapping[str, Any],
        cursor: ListenerCursor,
        gateway_url: str,
    ) -> bool:
        """Handle QQ dispatch events and persist cursor state."""
        if event_type == "READY":
            await self._handle_ready_event(
                data=data, cursor=cursor, gateway_url=gateway_url
            )
            return False

        if event_type == "RESUMED":
            await self._repository.save_listener_cursor(cursor)
            return False

        normalized = normalize_qq_event(self.subscription, event_type, data)
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
        gateway_url: str,
    ) -> None:
        """Persist QQ READY event session state."""
        session_id = data.get("session_id")
        if isinstance(session_id, str):
            cursor.qq_session_id = session_id
        cursor.qq_resume_gateway_url = gateway_url
        user = data.get("user")
        if isinstance(user, Mapping):
            user_id = user.get("id")
            if user_id is not None:
                self._bot_user_id = str(user_id)
        await self._repository.save_listener_cursor(cursor)

    async def _receive_gateway_payload(
        self,
        websocket: QQGatewayConnection,
    ) -> dict[str, Any]:
        """Receive and decode a QQ Gateway frame."""
        return _decode_gateway_payload(await websocket.recv())

    async def _send_gateway_payload(
        self,
        websocket: QQGatewayConnection,
        payload: dict[str, Any],
    ) -> None:
        """Serialize and send a QQ Gateway frame."""
        self._last_polled_at = _utcnow()
        await websocket.send(json.dumps(payload))


def qq_intents_bitmask(event_types: list[str]) -> int:
    """Convert configured QQ event names into a Gateway bitmask."""
    bitmask = 0
    for item in event_types:
        bitmask |= _QQ_EVENT_INTENT_BITS.get(str(item).strip().upper(), 0)
    return bitmask


def normalize_qq_event(
    subscription: ListenerSubscription,
    event_type: str,
    event: Mapping[str, Any],
) -> ListenerDispatchPayload | None:
    """Normalize a QQ dispatch event into the shared listener payload."""
    allowed_events = {
        str(value).strip().upper()
        for value in subscription.config.get("allowed_events", [])
        if str(value).strip()
    }
    event_name = event_type.strip().upper()
    if allowed_events and event_name not in allowed_events:
        return None

    scene_type = _qq_scene_type(event_name)
    if scene_type is None:
        return None

    allowed_scene_types = {
        str(value).strip().lower()
        for value in subscription.config.get("allowed_scene_types", [])
        if str(value).strip()
    }
    if allowed_scene_types and scene_type not in allowed_scene_types:
        return None

    message_id = _string_or_none(event.get("id"))
    if message_id is None:
        return None
    author = event.get("author", {})
    if not isinstance(author, Mapping):
        author = {}
    content = _string_or_none(event.get("content"))

    return _build_qq_dispatch_payload(
        subscription=subscription,
        event_type=event_name,
        event=event,
        scene_type=scene_type,
        message_id=message_id,
        author=author,
        content=content,
    )


def _build_qq_dispatch_payload(
    *,
    subscription: ListenerSubscription,
    event_type: str,
    event: Mapping[str, Any],
    scene_type: Literal["c2c", "group", "channel"],
    message_id: str,
    author: Mapping[str, Any],
    content: str | None,
) -> ListenerDispatchPayload | None:
    """Build the normalized dispatch payload for a QQ message event."""
    if scene_type == "c2c":
        user_openid = _string_or_none(author.get("user_openid"))
        if user_openid is None:
            return None
        reply_target = {
            "openid": user_openid,
            "msg_id": message_id,
            "msg_seq": 1,
        }
        message = ListenerDispatchMessage(
            chat_id=user_openid,
            user_id=user_openid,
            text=content,
            chat_type="c2c",
            metadata={"scene_type": scene_type},
        )
    elif scene_type == "group":
        group_openid = _string_or_none(event.get("group_openid"))
        member_openid = _string_or_none(author.get("member_openid"))
        if group_openid is None:
            return None
        reply_target = {
            "group_openid": group_openid,
            "msg_id": message_id,
            "msg_seq": 1,
        }
        message = ListenerDispatchMessage(
            chat_id=group_openid,
            user_id=member_openid,
            text=content,
            chat_type="group",
            metadata={"scene_type": scene_type},
        )
    else:
        channel_id = _string_or_none(event.get("channel_id"))
        guild_id = _string_or_none(event.get("guild_id"))
        if channel_id is None:
            return None
        reply_target = {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "msg_id": message_id,
        }
        message = ListenerDispatchMessage(
            chat_id=channel_id,
            channel_id=channel_id,
            guild_id=guild_id,
            user_id=_string_or_none(author.get("id")),
            username=_string_or_none(author.get("username")),
            text=content,
            chat_type="channel",
            metadata={"scene_type": scene_type},
        )

    return ListenerDispatchPayload(
        platform=ListenerPlatform.QQ,
        event_type=event_type,
        dedupe_key=f"qq:message:{event_type}:{message_id}",
        bot_identity=subscription.bot_identity_key,
        message=message,
        reply_target=reply_target,
        raw_event=dict(event),
        metadata={
            "node_name": subscription.node_name,
            "scene_type": scene_type,
        },
    )


def _qq_scene_type(
    event_type: str,
) -> Literal["c2c", "group", "channel"] | None:
    """Return the high-level reply scene for the QQ event type."""
    if event_type == "C2C_MESSAGE_CREATE":
        return "c2c"
    if event_type == "GROUP_AT_MESSAGE_CREATE":
        return "group"
    if event_type in {"AT_MESSAGE_CREATE", "MESSAGE_CREATE"}:
        return "channel"
    return None


def _decode_gateway_payload(frame: str | bytes) -> dict[str, Any]:
    """Deserialize a QQ Gateway frame into a mapping payload."""
    if isinstance(frame, bytes):
        frame = frame.decode("utf-8")
    payload = json.loads(frame)
    if not isinstance(payload, dict):
        msg = "QQ Gateway frame was not a JSON object"
        raise ValueError(msg)
    return payload


def _extract_heartbeat_interval(payload: Mapping[str, Any]) -> float:
    """Return the heartbeat interval from a QQ HELLO payload."""
    if payload.get("op") != 10:
        msg = "QQ Gateway did not start with HELLO"
        raise ValueError(msg)
    data = payload.get("d", {})
    if not isinstance(data, Mapping):
        msg = "QQ HELLO payload did not include a heartbeat interval"
        raise ValueError(msg)
    heartbeat_interval = data.get("heartbeat_interval")
    if not isinstance(heartbeat_interval, int | float):
        msg = "QQ heartbeat interval was missing or invalid"
        raise ValueError(msg)
    return max(float(heartbeat_interval) / 1000, 0.01)


def _string_or_none(value: object) -> str | None:
    """Return a string value or ``None`` if the value is missing."""
    if value is None:
        return None
    return str(value)


__all__ = [
    "DefaultQQAccessTokenHttpClient",
    "DefaultQQAccessTokenProvider",
    "DefaultQQGatewayConnector",
    "DefaultQQGatewayHttpClient",
    "QQAccessTokenHttpClient",
    "QQAccessTokenPayload",
    "QQAccessTokenProvider",
    "QQGatewayAdapter",
    "QQGatewayConnection",
    "QQGatewayConnector",
    "QQGatewayHttpClient",
    "QQGatewayInfo",
    "QQGatewaySessionStartLimit",
    "normalize_qq_event",
    "qq_intents_bitmask",
]
