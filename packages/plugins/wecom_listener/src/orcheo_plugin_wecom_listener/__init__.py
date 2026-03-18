"""WeCom listener plugin using WebSocket long-connection."""

from __future__ import annotations
import asyncio
import logging
import os
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4
from pydantic import Field
from orcheo.listeners.models import (
    ListenerDispatchMessage,
    ListenerDispatchPayload,
    ListenerHealthSnapshot,
    ListenerSubscription,
)
from orcheo.listeners.registry import ListenerMetadata, default_listener_compiler
from orcheo.nodes.base import TaskNode
from orcheo.nodes.listeners import ListenerNode
from orcheo.nodes.registry import NodeMetadata
from orcheo.plugins import PluginAPI


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from asyncio import AbstractEventLoop


# ---------------------------------------------------------------------------
# Process-global client registry
# ---------------------------------------------------------------------------

_WECOM_CLIENT_REGISTRY: dict[str, tuple[Any, AbstractEventLoop]] = {}
_REGISTRY_LOCK = threading.Lock()


def register_wecom_client(
    subscription_id: str,
    client: Any,
    loop: AbstractEventLoop,
) -> None:
    """Register a WSClient so reply nodes can look it up."""
    with _REGISTRY_LOCK:
        _WECOM_CLIENT_REGISTRY[subscription_id] = (client, loop)


def deregister_wecom_client(subscription_id: str) -> None:
    """Remove a WSClient entry when the adapter stops."""
    with _REGISTRY_LOCK:
        _WECOM_CLIENT_REGISTRY.pop(subscription_id, None)


def get_wecom_client(
    subscription_id: str,
) -> tuple[Any, AbstractEventLoop] | None:
    """Return the registered ``(WSClient, sdk_loop)`` or ``None``."""
    with _REGISTRY_LOCK:
        return _WECOM_CLIENT_REGISTRY.get(subscription_id)


def _optional_string(value: Any) -> str | None:
    """Return a stripped string or ``None`` when empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _handle_wecom_text_preview(body: Mapping[str, Any]) -> str | None:
    """Extract text from a text frame body, if available."""
    text_obj = body.get("text")
    if isinstance(text_obj, Mapping):
        return _optional_string(text_obj.get("content"))
    return _optional_string(text_obj)


def _handle_wecom_voice_preview(body: Mapping[str, Any]) -> str:
    """Provide a textual description for voice frames."""
    voice_obj = body.get("voice")
    if isinstance(voice_obj, Mapping):
        content = _optional_string(voice_obj.get("content"))
        if content:
            return content
    return "[Voice]"


def _handle_wecom_file_preview(body: Mapping[str, Any]) -> str:
    """Provide a textual description for file frames."""
    file_obj = body.get("file")
    if isinstance(file_obj, Mapping):
        file_name = _optional_string(file_obj.get("file_name"))
        if file_name:
            return f"[File] {file_name}"
    return "[File]"


def _handle_wecom_image_preview(_: Mapping[str, Any]) -> str:
    """Provide a placeholder text for image frames."""
    return "[Image]"


def _handle_wecom_mixed_preview(_: Mapping[str, Any]) -> str:
    """Provide a placeholder text for mixed frames."""
    return "[Mixed]"


_WECOM_FRAME_TEXT_HANDLERS: dict[str, Callable[[Mapping[str, Any]], str | None]] = {
    "text": _handle_wecom_text_preview,
    "image": _handle_wecom_image_preview,
    "voice": _handle_wecom_voice_preview,
    "file": _handle_wecom_file_preview,
    "mixed": _handle_wecom_mixed_preview,
}


class _SharedWeComSdkLoop:
    """Own a single SDK event loop for all WeCom listeners in one process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: AbstractEventLoop | None = None
        self._ref_count = 0

    def acquire(self) -> AbstractEventLoop:
        """Return the shared SDK loop, starting it on demand."""
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._ready.clear()
                self._thread = threading.Thread(
                    target=self._run,
                    name="wecom-sdk-loop",
                    daemon=True,
                )
                self._thread.start()
            self._ref_count += 1
        self._ready.wait(timeout=5)
        if self._loop is None:  # pragma: no cover - defensive
            raise RuntimeError("Failed to start the shared WeCom SDK event loop.")
        return self._loop

    def release(self) -> None:
        """Release one shared-loop reference and stop when unused."""
        loop: AbstractEventLoop | None = None
        thread: threading.Thread | None = None
        with self._lock:
            if self._ref_count > 0:
                self._ref_count -= 1
            if self._ref_count == 0 and self._loop is not None:
                loop = self._loop
                thread = self._thread
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5)

    def shutdown(self) -> None:
        """Force-stop the shared loop. Used by tests and process shutdown."""
        with self._lock:
            self._ref_count = 0
            loop = self._loop
            thread = self._thread
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
            self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                with suppress(Exception):
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            loop.close()
            with self._lock:
                if self._loop is loop:
                    self._loop = None
                    self._thread = None
                    self._ready.clear()


_SHARED_WECOM_SDK_LOOP = _SharedWeComSdkLoop()


def get_wecom_long_connection_block_reason(
    config: Mapping[str, Any],
) -> str | None:
    """Return a blocking reason when the WeCom bot config is incomplete."""
    bot_id = str(config.get("bot_id", "")).strip()
    bot_secret = str(config.get("bot_secret", "")).strip()
    if not bot_id:
        return "WeCom bot_id is missing in listener configuration."
    if not bot_secret:
        return "WeCom bot_secret is missing in listener configuration."
    return None


def _extract_frame_text(frame: Mapping[str, Any]) -> str | None:
    """Return a text form suitable for downstream agent processing."""
    body = frame.get("body")
    if not isinstance(body, Mapping):
        return None
    msg_type = str(frame.get("msgtype", "")).strip().lower()
    if not msg_type:
        for key in ("text", "image", "voice", "file", "mixed"):
            if key in body:
                msg_type = key
                break
    handler = _WECOM_FRAME_TEXT_HANDLERS.get(msg_type)
    if handler is None:
        return None
    return handler(body)


def normalize_wecom_test_event(
    subscription: ListenerSubscription,
    event: dict[str, Any],
    *,
    index: int,
) -> ListenerDispatchPayload:
    """Normalize one fixture WeCom event into the shared listener payload."""
    chat_id = _optional_string(event.get("chat_id") or event.get("conversation_id"))
    to_user = (
        None
        if chat_id
        else _optional_string(
            event.get("to_user") or event.get("external_userid") or "wecom-user"
        )
    )
    text = str(event.get("text", "hello from wecom"))
    dedupe_target = chat_id or to_user or "unknown"
    dedupe_key = f"{subscription.id}:wecom:{index}:{dedupe_target}"
    return ListenerDispatchPayload(
        platform="wecom",
        event_type="message",
        dedupe_key=dedupe_key,
        bot_identity=subscription.bot_identity_key,
        listener_subscription_id=subscription.id,
        message=ListenerDispatchMessage(
            user_id=to_user,
            username=str(event.get("username", to_user or chat_id or "wecom-user")),
            text=text,
            chat_id=chat_id or to_user,
            chat_type="group" if chat_id else "private",
            metadata={"source": "wecom-plugin"},
        ),
        reply_target={
            "platform": "wecom",
            "chat_id": chat_id,
            "to_user": to_user,
        },
        raw_event=event,
        metadata={"provider": "wecom", "transport": "fixture"},
    )


def normalize_wecom_ws_event(
    subscription: ListenerSubscription,
    frame: Mapping[str, Any],
) -> ListenerDispatchPayload | None:
    """Normalize a WeCom WebSocket frame into the shared listener payload."""
    text = _extract_frame_text(frame)
    if text is None:
        return None

    body = frame.get("body") or {}
    msg_type = str(frame.get("msgtype", "message")).strip().lower()
    from_user = _optional_string(body.get("from", {}).get("user_id")) or "wecom-user"
    chat_id = _optional_string(body.get("chat_id"))
    to_user = None if chat_id else from_user
    msg_id = _optional_string(body.get("msg_id"))
    dedupe_source = msg_id or f"{from_user}:{chat_id or from_user}:{msg_type}"

    return ListenerDispatchPayload(
        platform="wecom",
        event_type=msg_type,
        dedupe_key=f"{subscription.id}:wecom:{dedupe_source}",
        bot_identity=subscription.bot_identity_key,
        listener_subscription_id=subscription.id,
        message=ListenerDispatchMessage(
            chat_id=chat_id or from_user,
            message_id=msg_id,
            user_id=from_user,
            username=from_user,
            text=text,
            chat_type="group" if chat_id else "private",
            metadata={
                "msg_type": msg_type,
            },
        ),
        reply_target={
            "platform": "wecom",
            "chat_id": chat_id,
            "to_user": to_user,
        },
        raw_event=dict(frame),
        metadata={"provider": "wecom", "transport": "websocket"},
    )


class WeComListenerPluginNode(ListenerNode):
    """Declare a WeCom listener subscription from an external plugin package."""

    platform: str = "wecom"
    bot_id: str = "[[wecom_bot_id]]"
    bot_secret: str = "[[wecom_bot_secret]]"
    test_events: list[dict[str, Any]] = Field(default_factory=list)


_DEFAULT_BACKEND_URL = "http://backend:8000"
_BACKEND_URL_ENV = "ORCHEO_BACKEND_INTERNAL_URL"


def build_wecom_ws_reply_body(message: str) -> dict[str, Any]:
    """Build a valid one-shot WeCom websocket reply payload.

    The websocket reply API does not accept plain ``msgtype=text`` bodies for
    normal message replies. A completed ``stream`` reply is the compatible
    single-message form for this channel.
    """
    return {
        "msgtype": "stream",
        "stream": {
            "id": f"orcheo-{uuid4()}",
            "content": message,
            "finish": True,
        },
    }


class WeComWsReplyNode(TaskNode):
    """Reply to a WeCom message via the WebSocket long-connection."""

    message: str = Field(description="Reply text content")
    raw_event: dict[str, Any] | str = Field(
        default_factory=dict,
        description="Original WS frame dict for threaded reply",
    )
    subscription_id: str = ""

    async def run(self, state: Any, config: Any) -> dict[str, Any]:
        """Send a reply through the backend's active WSClient.

        The WSClient lives in the backend process while this node executes
        in the Celery worker.  When a local client is available (same process),
        we use it directly; otherwise we relay via the backend HTTP endpoint.
        """
        del state, config
        sub_id = str(self.subscription_id)

        # Fast path: same-process (unit tests or single-process dev server).
        entry = get_wecom_client(sub_id)
        if entry is not None:
            client, sdk_loop = entry
            body = build_wecom_ws_reply_body(self.message)
            future = asyncio.run_coroutine_threadsafe(
                client.reply(self.raw_event, body),
                sdk_loop,
            )
            await asyncio.wrap_future(future)
            return {"sent": True}

        # Slow path: relay through the backend process via HTTP.
        return await self._relay_via_backend(sub_id)

    async def _relay_via_backend(self, subscription_id: str) -> dict[str, Any]:
        """POST the reply payload to the backend's internal relay endpoint."""
        import httpx

        backend_url = os.environ.get(_BACKEND_URL_ENV, _DEFAULT_BACKEND_URL)
        url = f"{backend_url}/api/internal/listeners/wecom/reply"
        raw = self.raw_event if isinstance(self.raw_event, dict) else {}
        payload = {
            "subscription_id": subscription_id,
            "message": self.message,
            "raw_event": raw,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
        if response.status_code != 200:
            detail = response.text
            raise RuntimeError(
                f"Backend WeCom reply relay failed "
                f"(HTTP {response.status_code}): {detail}"
            )
        return {"sent": True}


class WeComListenerAdapter:
    """Receive WeCom events through a managed WebSocket long-connection."""

    def __init__(
        self,
        *,
        repository: Any,
        subscription: ListenerSubscription,
        runtime_id: str,
    ) -> None:
        """Initialize the adapter for one WeCom listener subscription."""
        self._repository = repository
        self.subscription = subscription
        self._runtime_id = runtime_id
        self._status = "starting"
        self._detail: str | None = None
        self._last_event_at: datetime | None = None
        self._dispatch_loop: AbstractEventLoop | None = None
        self._sdk_loop: AbstractEventLoop | None = None
        self._sdk_client: Any = None
        self._sdk_connect_future: Future[Any] | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        """Dispatch fixtures or start the WebSocket long-connection until stopped."""
        self._dispatch_loop = asyncio.get_running_loop()
        events = self.subscription.config.get("test_events", [])
        if isinstance(events, list) and events:
            await self._run_fixture_mode(events=events, stop_event=stop_event)
            return
        await self._run_websocket_connection(stop_event)

    async def _run_fixture_mode(
        self,
        *,
        events: list[Any],
        stop_event: asyncio.Event,
    ) -> None:
        self._status = "healthy"
        self._detail = "running in fixture mode"
        for index, item in enumerate(events):
            if stop_event.is_set():
                break
            event = item if isinstance(item, dict) else {"text": str(item)}
            payload = normalize_wecom_test_event(
                self.subscription,
                event,
                index=index,
            )
            await self._repository.dispatch_listener_event(
                self.subscription.id,
                payload,
            )
            self._last_event_at = datetime.now()
        await stop_event.wait()
        self._status = "stopped"

    async def _run_websocket_connection(
        self,
        stop_event: asyncio.Event,
    ) -> None:
        block_reason = get_wecom_long_connection_block_reason(self.subscription.config)
        if block_reason is not None:
            self._status = "error"
            self._detail = f"blocked: {block_reason}"
            logger.warning(
                "WeCom listener subscription %s is blocked: %s",
                self.subscription.id,
                block_reason,
            )
            await stop_event.wait()
            self._status = "stopped"
            return

        try:
            from wecom_aibot_sdk import WSClient
        except ImportError as exc:  # pragma: no cover - defensive
            raise RuntimeError(
                "The WeCom listener plugin requires the 'wecom-aibot-sdk' "
                "package for long-connection mode."
            ) from exc

        self._sdk_loop = _SHARED_WECOM_SDK_LOOP.acquire()
        self._sdk_client = WSClient(
            bot_id=str(self.subscription.config.get("bot_id", "")),
            secret=str(self.subscription.config.get("bot_secret", "")),
        )

        def handle_message(frame: Any) -> None:
            self._handle_ws_event(frame)

        for event_type in (
            "message.text",
            "message.image",
            "message.voice",
            "message.file",
            "message.mixed",
        ):
            self._sdk_client.on(event_type, handle_message)

        try:
            connect_future = asyncio.run_coroutine_threadsafe(
                self._sdk_client.connect(),
                self._sdk_loop,
            )
            await asyncio.wait_for(
                asyncio.wrap_future(connect_future),
                timeout=30,
            )
            register_wecom_client(
                str(self.subscription.id),
                self._sdk_client,
                self._sdk_loop,
            )
            self._status = "healthy"
            self._detail = "connected to WeCom long-connection"
            await stop_event.wait()
        except BaseException as exc:
            self._status = "error"
            self._detail = str(exc)
            raise
        finally:
            deregister_wecom_client(str(self.subscription.id))
            self._stop_ws_client()
            _SHARED_WECOM_SDK_LOOP.release()
            self._sdk_loop = None
            self._sdk_client = None
            self._sdk_connect_future = None
        self._status = "stopped"

    def _handle_ws_event(self, frame: Any) -> None:
        if self._dispatch_loop is None:
            return
        frame_dict = frame if isinstance(frame, dict) else {}
        payload = normalize_wecom_ws_event(self.subscription, frame_dict)
        if payload is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            self._repository.dispatch_listener_event(
                self.subscription.id,
                payload,
            ),
            self._dispatch_loop,
        )
        future.result(timeout=30)
        self._last_event_at = datetime.now()
        self._status = "healthy"
        self._detail = None

    def _stop_ws_client(self) -> None:
        if self._sdk_loop is None or self._sdk_client is None:
            return
        with suppress(Exception):
            future = asyncio.run_coroutine_threadsafe(
                self._sdk_client.disconnect(),
                self._sdk_loop,
            )
            future.result(timeout=5)

    def health(self) -> ListenerHealthSnapshot:
        """Return the current adapter health snapshot."""
        return ListenerHealthSnapshot(
            subscription_id=self.subscription.id,
            runtime_id=self._runtime_id,
            status=self._status,
            platform=self.subscription.platform,
            last_event_at=self._last_event_at,
            detail=self._detail,
        )


class WeComListenerPlugin:
    """Plugin entry point for the WeCom listener package."""

    def register(self, api: PluginAPI) -> None:
        """Register the WeCom listener node and adapter factory."""
        api.register_node(
            NodeMetadata(
                name="WeComListenerPluginNode",
                description="Receive WeCom events through the plugin contract.",
                category="trigger",
            ),
            WeComListenerPluginNode,
        )
        api.register_node(
            NodeMetadata(
                name="WeComWsReplyNode",
                description="Reply to WeCom messages via WebSocket long-connection.",
                category="messaging",
            ),
            WeComWsReplyNode,
        )
        api.register_listener(
            ListenerMetadata(
                id="wecom",
                display_name="WeCom Listener",
                description=("Receive WeCom events via WebSocket long-connection."),
            ),
            default_listener_compiler,
            lambda *, repository, subscription, runtime_id: WeComListenerAdapter(
                repository=repository,
                subscription=subscription,
                runtime_id=runtime_id,
            ),
        )


plugin = WeComListenerPlugin()
