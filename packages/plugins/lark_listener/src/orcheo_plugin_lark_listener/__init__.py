"""Lark listener plugin."""

from __future__ import annotations
import asyncio
import json
import logging
import threading
from collections.abc import Mapping
from concurrent.futures import Future
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from pydantic import Field
from orcheo.listeners.models import (
    ListenerDispatchMessage,
    ListenerDispatchPayload,
    ListenerHealthSnapshot,
    ListenerSubscription,
)
from orcheo.listeners.registry import ListenerMetadata, default_listener_compiler
from orcheo.nodes.listeners import ListenerNode
from orcheo.nodes.registry import NodeMetadata
from orcheo.plugins import PluginAPI


LARK_OPEN_DOMAIN = "https://open.larksuite.com"
REQUIRED_LARK_MESSAGE_EVENTS = frozenset({"im.message.receive_v1", "message"})
_LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:
    from asyncio import AbstractEventLoop


class _SharedLarkSdkLoop:
    """Own a single SDK event loop for all Lark listeners in one process."""

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
                    name="lark-sdk-loop",
                    daemon=True,
                )
                self._thread.start()
            self._ref_count += 1
        self._ready.wait(timeout=5)
        if self._loop is None:  # pragma: no cover - defensive
            raise RuntimeError("Failed to start the shared Lark SDK event loop.")
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


_SHARED_LARK_SDK_LOOP = _SharedLarkSdkLoop()


def _request_json(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    body: Mapping[str, Any] | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """Perform an HTTP request and decode a JSON payload."""
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=payload, headers=request_headers, method=method)
    with urlopen(request, timeout=timeout) as response:  # nosec B310
        raw = response.read().decode("utf-8")
    if not raw:
        return {}
    data = json.loads(raw)
    if isinstance(data, dict):
        return data
    return {"data": data}


def _extract_lark_message_text(content: Any) -> str | None:
    """Return a text preview from the raw Lark message content."""
    if not content:
        return None
    if isinstance(content, Mapping):
        return _extract_text_from_mapping(content)
    if not isinstance(content, str):
        return str(content)
    return _extract_text_from_json(content)


def _extract_text_from_mapping(content: Mapping[str, Any]) -> str | None:
    """Extract ``text`` from mapping-style payloads."""
    text = content.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return None


def _extract_text_from_json(content: str) -> str:
    """Decode a JSON payload and return its ``text`` value if available."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content
    if isinstance(payload, Mapping):
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            return text
    return content


def _event_value(container: Any, key: str) -> Any:
    """Read ``key`` from either mapping-style or attribute-style payloads."""
    if isinstance(container, Mapping):
        return container.get(key)
    return getattr(container, key, None)


def _coalesce_event_values(
    containers: tuple[Any, ...], keys: tuple[str, ...]
) -> Any | None:
    """Return the first non-``None`` value found for the requested keys."""
    for container in containers:
        if container is None:
            continue
        for key in keys:
            value = _event_value(container, key)
            if value is not None:
                return value
    return None


def _lark_api_error_message(payload: Mapping[str, Any]) -> str:
    """Return a concise, user-facing Lark API error."""
    code = _event_value(payload, "code")
    message = _event_value(payload, "msg")
    return f"code={code}, msg={message}"


def _normalize_lark_domain(domain_value: Any) -> str:
    """Normalize the configured domain and fall back to the default host."""
    raw_domain = str(domain_value or LARK_OPEN_DOMAIN).strip()
    normalized = raw_domain.rstrip("/")
    return normalized or LARK_OPEN_DOMAIN


def _lark_payload_failure_reason(payload: Mapping[str, Any], prefix: str) -> str | None:
    """Return a failure message when the provided payload reports an error."""
    if _event_value(payload, "code") == 0:
        return None
    return f"{prefix}{_lark_api_error_message(payload)}"


def _get_tenant_access_token(
    domain: str, app_id: str, app_secret: str
) -> tuple[str | None, str | None]:
    """Authenticate with Lark and return the tenant access token."""
    token_payload = _request_json(
        "POST",
        f"{domain}/open-apis/auth/v3/tenant_access_token/internal",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    failure_reason = _lark_payload_failure_reason(
        token_payload, "Failed to authenticate with Lark OpenAPI; "
    )
    if failure_reason:
        return None, failure_reason
    tenant_access_token = _event_value(token_payload, "tenant_access_token")
    if not tenant_access_token:
        return None, "Lark OpenAPI did not return a tenant_access_token."
    return tenant_access_token, None


def _fetch_lark_app_data(
    domain: str, app_id: str, tenant_access_token: str
) -> tuple[Mapping[str, Any] | None, str | None]:
    """Fetch the configured Lark application metadata."""
    app_payload = _request_json(
        "GET",
        f"{domain}/open-apis/application/v6/applications/{app_id}?lang=en_us",
        headers={"Authorization": f"Bearer {tenant_access_token}"},
    )
    failure_reason = _lark_payload_failure_reason(
        app_payload, "Failed to fetch Lark app metadata; "
    )
    if failure_reason:
        return None, failure_reason
    return (
        _event_value(_event_value(app_payload, "data"), "app"),
        None,
    )


def _fetch_lark_app_version_data(
    domain: str, app_id: str, online_version_id: str, tenant_access_token: str
) -> tuple[Mapping[str, Any] | None, str | None]:
    """Fetch the published version metadata for the Lark application."""
    version_payload = _request_json(
        "GET",
        (
            f"{domain}/open-apis/application/v6/applications/{app_id}/"
            f"app_versions/{online_version_id}?lang=en_us"
        ),
        headers={"Authorization": f"Bearer {tenant_access_token}"},
    )
    failure_reason = _lark_payload_failure_reason(
        version_payload, "Failed to fetch Lark app version metadata; "
    )
    if failure_reason:
        return None, failure_reason
    return (
        _event_value(_event_value(version_payload, "data"), "app_version"),
        None,
    )


def _collect_normalized_events(app_version_data: Any) -> set[str]:
    """Collect event names from the published app version metadata."""
    normalized_events: set[str] = set()
    if isinstance(app_version_data, Mapping):
        events = _event_value(app_version_data, "events")
        if isinstance(events, list):
            normalized_events.update(
                str(event_name).strip()
                for event_name in events
                if str(event_name).strip()
            )

        event_infos = _event_value(app_version_data, "event_infos")
        if isinstance(event_infos, list):
            for event_info in event_infos:
                event_type = _event_value(event_info, "event_type")
                if isinstance(event_type, str) and event_type.strip():
                    normalized_events.add(event_type.strip())
    return normalized_events


def _validate_lark_credentials(
    config: Mapping[str, Any],
) -> tuple[str, str, str | None]:
    """Ensure the listener config includes the required app credentials."""
    app_id = str(config.get("app_id", "")).strip()
    if not app_id:
        return "", "", "Lark app_id is missing in listener configuration."

    app_secret = str(config.get("app_secret", "")).strip()
    if not app_secret:
        return app_id, "", "Lark app_secret is missing in listener configuration."

    return app_id, app_secret, None


def _run_lark_subscription_preflight(
    domain: str, app_id: str, app_secret: str
) -> str | None:
    """Perform the OpenAPI checks that validate message subscriptions."""
    reason: str | None = None
    try:
        tenant_access_token, reason = _get_tenant_access_token(
            domain, app_id, app_secret
        )
        if reason is None:
            assert tenant_access_token is not None  # for mypy
            app_data, reason = _fetch_lark_app_data(domain, app_id, tenant_access_token)
            if reason is None:
                callback_info = _event_value(app_data, "callback_info")
                callback_type = (
                    str(_event_value(callback_info, "callback_type") or "")
                    .strip()
                    .lower()
                )
                if callback_type and callback_type != "websocket":
                    reason = (
                        f"Lark app callback_type is '{callback_type}', expected "
                        "'websocket' for long-connection mode."
                    )
                else:
                    online_version_id = _event_value(app_data, "online_version_id")
                    if not online_version_id:
                        reason = (
                            "Lark app has no published version; publish the app first."
                        )
                    else:
                        app_version_data, reason = _fetch_lark_app_version_data(
                            domain,
                            app_id,
                            online_version_id,
                            tenant_access_token,
                        )
                        if reason is None:
                            normalized_events = _collect_normalized_events(
                                app_version_data
                            )
                            if REQUIRED_LARK_MESSAGE_EVENTS.isdisjoint(
                                normalized_events
                            ):
                                current_events = (
                                    ", ".join(sorted(normalized_events))
                                    if normalized_events
                                    else "none"
                                )
                                reason = (
                                    "Lark published app version does not subscribe to "
                                    "message receive events. Add "
                                    "`im.message.receive_v1` in Lark Open Platform, "
                                    "publish the app, then retry. "
                                    f"Current events: {current_events}."
                                )
    except (json.JSONDecodeError, OSError, URLError) as exc:
        _LOGGER.warning(
            (
                "Skipping Lark message-subscription preflight check due to request "
                "error: %s"
            ),
            exc,
        )
        return None

    return reason


def get_lark_long_connection_block_reason(config: Mapping[str, Any]) -> str | None:
    """Return a reason why the Lark app cannot handle message events."""
    app_id, app_secret, credential_reason = _validate_lark_credentials(config)
    if credential_reason is not None:
        return credential_reason

    domain = _normalize_lark_domain(config.get("domain"))
    return _run_lark_subscription_preflight(domain, app_id, app_secret)


def normalize_lark_test_event(
    subscription: ListenerSubscription,
    event: dict[str, Any],
    *,
    index: int,
) -> ListenerDispatchPayload:
    """Normalize one fixture Lark event into the shared listener payload."""
    open_id = str(event.get("open_id", "lark-user"))
    chat_id = str(event.get("chat_id", "lark-chat"))
    text = str(event.get("text", "hello from lark"))
    dedupe_key = f"{subscription.id}:lark:{index}:{chat_id}"
    return ListenerDispatchPayload(
        platform="lark",
        event_type="im.message.receive_v1",
        dedupe_key=dedupe_key,
        bot_identity=subscription.bot_identity_key,
        listener_subscription_id=subscription.id,
        message=ListenerDispatchMessage(
            user_id=open_id,
            username=str(event.get("username", open_id)),
            text=text,
            chat_id=chat_id,
            metadata={"source": "lark-plugin"},
        ),
        reply_target={
            "platform": "lark",
            "chat_id": chat_id,
            "open_id": open_id,
            "app_id": subscription.config.get("app_id"),
        },
        raw_event=event,
        metadata={"provider": "lark", "transport": "fixture"},
    )


def normalize_lark_sdk_event(
    subscription: ListenerSubscription,
    event: Any,
) -> ListenerDispatchPayload:
    """Normalize an official Lark long-connection event into shared payload."""
    event_data = _event_value(event, "event")
    header = _event_value(event, "header")
    sender = _event_value(event_data, "sender")
    sender_id = _event_value(sender, "sender_id")
    message = _event_value(event_data, "message")

    open_id = _coalesce_event_values(
        (sender_id, sender),
        ("open_id", "user_id", "union_id"),
    )
    open_id = str(open_id or "lark-user")

    chat_id = _coalesce_event_values(
        (message, event_data),
        ("chat_id",),
    )
    chat_id = str(chat_id or "lark-chat")

    raw_message_id = _coalesce_event_values(
        (message, event_data),
        ("message_id",),
    )
    event_id = _coalesce_event_values(
        (header, event),
        ("event_id", "uuid"),
    )
    message_id = str(raw_message_id or event_id or f"{chat_id}:unknown")

    raw_content = _coalesce_event_values(
        (message, event_data),
        ("content",),
    )
    text = _extract_lark_message_text(raw_content) or "lark message"
    event_type = (
        _coalesce_event_values(
            (header, event),
            ("event_type", "type"),
        )
        or "im.message.receive_v1"
    )

    thread_id = _coalesce_event_values(
        (message, event_data),
        ("thread_id",),
    )

    chat_type = _coalesce_event_values(
        (message, event_data),
        ("chat_type",),
    )

    message_type = _coalesce_event_values(
        (message, event_data),
        ("message_type",),
    )

    tenant_key = _coalesce_event_values(
        (sender, header),
        ("tenant_key",),
    )

    dedupe_key = f"{subscription.id}:lark:{message_id}"
    reply_target = {
        "platform": "lark",
        "chat_id": chat_id,
        "open_id": open_id,
        "app_id": subscription.config.get("app_id"),
    }
    if raw_message_id:
        reply_target["message_id"] = str(raw_message_id)
    if thread_id:
        reply_target["thread_id"] = thread_id

    return ListenerDispatchPayload(
        platform="lark",
        event_type=str(event_type),
        dedupe_key=dedupe_key,
        bot_identity=subscription.bot_identity_key,
        listener_subscription_id=subscription.id,
        message=ListenerDispatchMessage(
            user_id=str(open_id),
            username=str(open_id),
            text=text,
            chat_id=str(chat_id),
            message_id=str(message_id),
            chat_type=str(chat_type) if chat_type is not None else None,
            metadata={
                "message_type": (
                    str(message_type) if message_type is not None else None
                ),
                "thread_id": thread_id,
                "tenant_key": tenant_key,
            },
        ),
        reply_target=reply_target,
        raw_event={
            "event_type": event_type,
            "message_id": message_id,
            "chat_id": chat_id,
            "chat_type": chat_type,
            "message_type": message_type,
            "content": raw_content,
            "open_id": open_id,
            "tenant_key": tenant_key,
        },
        metadata={"provider": "lark", "transport": "official-long-connection"},
    )


class LarkListenerPluginNode(ListenerNode):
    """Declare a Lark listener subscription from an external plugin package."""

    platform: str = "lark"
    app_id: str = "[[lark_app_id]]"
    app_secret: str = "[[lark_app_secret]]"
    domain: str = LARK_OPEN_DOMAIN
    test_events: list[dict[str, Any]] = Field(default_factory=list)


class LarkListenerAdapter:
    """Lark long-connection adapter using the official SDK."""

    def __init__(
        self,
        *,
        repository: Any,
        subscription: ListenerSubscription,
        runtime_id: str,
    ) -> None:
        """Initialize adapter state for a Lark listener subscription."""
        self._repository = repository
        self.subscription = subscription
        self._runtime_id = runtime_id
        self._status = "starting"
        self._detail: str | None = None
        self._last_event_at: datetime | None = None
        self._dispatch_loop: AbstractEventLoop | None = None
        self._sdk_loop: AbstractEventLoop | None = None
        self._sdk_client: Any = None
        self._sdk_ping_future: Future[Any] | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        """Dispatch fixture events or start the official Lark long connection."""
        self._dispatch_loop = asyncio.get_running_loop()
        events = self.subscription.config.get("test_events", [])
        if isinstance(events, list) and events:
            await self._run_fixture_mode(events=events, stop_event=stop_event)
            return
        await self._run_official_long_connection(stop_event)

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
            payload = normalize_lark_test_event(
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

    async def _run_official_long_connection(
        self,
        stop_event: asyncio.Event,
    ) -> None:
        block_reason = get_lark_long_connection_block_reason(self.subscription.config)
        if block_reason is not None:
            self._status = "error"
            self._detail = f"blocked: {block_reason}"
            _LOGGER.warning(
                "Lark listener subscription %s is blocked: %s",
                self.subscription.id,
                block_reason,
            )
            await stop_event.wait()
            self._status = "stopped"
            return

        try:
            import lark_oapi.ws.client as ws_client_module
            from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
            from lark_oapi.ws.client import Client as LarkWSClient
        except ImportError as exc:  # pragma: no cover - defensive
            raise RuntimeError(
                "The Lark listener plugin requires the official 'lark-oapi' "
                "package for long-connection mode."
            ) from exc
        self._sdk_loop = _SHARED_LARK_SDK_LOOP.acquire()
        ws_client_module.loop = self._sdk_loop

        def handle_message(event: Any) -> None:
            self._handle_official_event(event)

        dispatcher_builder = EventDispatcherHandler.builder("", "")
        if hasattr(dispatcher_builder, "register_p2_im_message_receive_v1"):
            dispatcher_builder = dispatcher_builder.register_p2_im_message_receive_v1(
                handle_message
            )
        elif hasattr(dispatcher_builder, "register_p2_customized_event"):
            dispatcher_builder = dispatcher_builder.register_p2_customized_event(
                "im.message.receive_v1",
                handle_message,
            )
        else:  # pragma: no cover - defensive
            raise RuntimeError(
                "Lark EventDispatcherHandler does not expose a compatible "
                "message registration hook."
            )
        if hasattr(dispatcher_builder, "register_p1_customized_event"):
            dispatcher_builder = dispatcher_builder.register_p1_customized_event(
                "message",
                handle_message,
            )
        dispatcher = dispatcher_builder.build()
        self._sdk_client = LarkWSClient(
            app_id=str(self.subscription.config.get("app_id", "")),
            app_secret=str(self.subscription.config.get("app_secret", "")),
            event_handler=dispatcher,
            domain=str(self.subscription.config.get("domain", LARK_OPEN_DOMAIN)),
            auto_reconnect=True,
        )
        try:
            connect_future = asyncio.run_coroutine_threadsafe(
                self._sdk_client._connect(),
                self._sdk_loop,
            )
            await asyncio.wait_for(
                asyncio.wrap_future(connect_future),
                timeout=30,
            )
            self._status = "healthy"
            self._detail = "connected to official Lark long connection"
            self._sdk_ping_future = asyncio.run_coroutine_threadsafe(
                self._sdk_client._ping_loop(),
                self._sdk_loop,
            )
            await stop_event.wait()
        except BaseException as exc:
            self._status = "error"
            self._detail = str(exc)
            raise
        finally:
            self._stop_official_client()
            _SHARED_LARK_SDK_LOOP.release()
            self._sdk_loop = None
            self._sdk_client = None
            self._sdk_ping_future = None
        self._status = "stopped"

    def _handle_official_event(self, event: Any) -> None:
        if self._dispatch_loop is None:
            return
        payload = normalize_lark_sdk_event(self.subscription, event)
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

    def _stop_official_client(self) -> None:
        if self._sdk_ping_future is not None:
            self._sdk_ping_future.cancel()
            with suppress(Exception):
                self._sdk_ping_future.result(timeout=5)
        if self._sdk_loop is None or self._sdk_client is None:
            return
        with suppress(Exception):
            future = asyncio.run_coroutine_threadsafe(
                self._sdk_client._disconnect(),
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


class LarkListenerPlugin:
    """Plugin entry point for the Lark validation package."""

    def register(self, api: PluginAPI) -> None:
        """Register the Lark listener node and adapter factory."""
        api.register_node(
            NodeMetadata(
                name="LarkListenerPluginNode",
                description="Receive Lark listener events through the plugin contract.",
                category="trigger",
            ),
            LarkListenerPluginNode,
        )
        api.register_listener(
            ListenerMetadata(
                id="lark",
                display_name="Lark Listener",
                description="Lark listener provided by a plugin package.",
            ),
            default_listener_compiler,
            lambda *, repository, subscription, runtime_id: LarkListenerAdapter(
                repository=repository,
                subscription=subscription,
                runtime_id=runtime_id,
            ),
        )


plugin = LarkListenerPlugin()
