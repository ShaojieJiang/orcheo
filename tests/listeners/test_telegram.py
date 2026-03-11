import asyncio
from typing import Any
from uuid import uuid4
import pytest
import orcheo.listeners.telegram as telegram_module
from orcheo.listeners import (
    ListenerCursor,
    ListenerDispatchPayload,
    ListenerPlatform,
    ListenerSubscription,
)
from orcheo.listeners.models import ListenerSubscriptionStatus
from orcheo.listeners.telegram import (
    DefaultTelegramPollingClient,
    TelegramPollingAdapter,
    normalize_telegram_update,
)


class DummyJsonResponse:
    def __init__(self, body: Any) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._body


class DummyTelegramAsyncClient:
    def __init__(self, *args: Any, response: Any = None, **kwargs: Any) -> None:
        self.response = response
        self.kwargs = kwargs
        self.post_calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> "DummyTelegramAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any]) -> DummyJsonResponse:
        self.post_calls.append((url, json))
        return DummyJsonResponse(self.response)


class TelegramRecordingRepository:
    def __init__(self) -> None:
        self.saved: list[ListenerCursor] = []
        self.dispatched: list[ListenerDispatchPayload] = []
        self.cursor: ListenerCursor | None = None

    async def get_listener_cursor(self, subscription_id: Any) -> ListenerCursor | None:
        return self.cursor

    async def save_listener_cursor(self, cursor: ListenerCursor) -> ListenerCursor:
        self.saved.append(cursor)
        self.cursor = cursor
        return cursor

    async def dispatch_listener_event(
        self, subscription_id: Any, payload: ListenerDispatchPayload
    ) -> Any:
        self.dispatched.append(payload)
        return payload


def telegram_subscription(**config: Any) -> ListenerSubscription:
    return ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="telegram",
        platform=ListenerPlatform.TELEGRAM,
        bot_identity_key="bot",
        config=config,
        status=ListenerSubscriptionStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_default_telegram_client_returns_empty_when_not_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory(*args: Any, **kwargs: Any) -> DummyTelegramAsyncClient:
        return DummyTelegramAsyncClient(response={"ok": False}, **kwargs)

    monkeypatch.setattr(telegram_module.httpx, "AsyncClient", factory)
    client = DefaultTelegramPollingClient()
    result = await client.get_updates(
        token="token",
        offset=None,
        timeout=5,
        allowed_updates=["message"],
        limit=10,
    )
    assert result == []


@pytest.mark.asyncio
async def test_default_telegram_client_filters_non_dict_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"ok": True, "result": ["bad", {"update_id": 1}]}

    def factory(*args: Any, **kwargs: Any) -> DummyTelegramAsyncClient:
        return DummyTelegramAsyncClient(response=body, **kwargs)

    monkeypatch.setattr(telegram_module.httpx, "AsyncClient", factory)
    client = DefaultTelegramPollingClient()
    updates = await client.get_updates(
        token="token",
        offset=5,
        timeout=10,
        allowed_updates=["message"],
        limit=2,
    )
    assert updates == [{"update_id": 1}]


@pytest.mark.asyncio
async def test_default_telegram_client_handles_bad_result_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"ok": True, "result": "not list"}

    def factory(*args: Any, **kwargs: Any) -> DummyTelegramAsyncClient:
        return DummyTelegramAsyncClient(response=body, **kwargs)

    monkeypatch.setattr(telegram_module.httpx, "AsyncClient", factory)
    client = DefaultTelegramPollingClient()
    assert (
        await client.get_updates(
            token="token",
            offset=None,
            timeout=10,
            allowed_updates=["message"],
            limit=2,
        )
        == []
    )


@pytest.mark.asyncio
async def test_default_telegram_client_includes_offset_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"ok": True, "result": [{"update_id": 1}]}
    clients: list[DummyTelegramAsyncClient] = []

    def factory(*args: Any, **kwargs: Any) -> DummyTelegramAsyncClient:
        instance = DummyTelegramAsyncClient(response=body, **kwargs)
        clients.append(instance)
        return instance

    monkeypatch.setattr(telegram_module.httpx, "AsyncClient", factory)
    client = DefaultTelegramPollingClient()
    await client.get_updates(
        token="token",
        offset=7,
        timeout=20,
        allowed_updates=["message", "edited_message"],
        limit=3,
    )
    assert clients[0].kwargs["timeout"] == 30
    payload = clients[0].post_calls[0][1]
    assert payload["timeout"] == 20
    assert payload["allowed_updates"] == ["message", "edited_message"]
    assert payload["limit"] == 3
    assert payload["offset"] == 7


def build_telegram_update(**kwargs: Any) -> dict[str, Any]:
    message = {
        "chat": {"id": 123, "type": "private"},
        "from": {"id": 456, "first_name": "Alex"},
        "text": "hi",
        "message_id": 55,
    }
    return {"update_id": 10, "message": message, **kwargs}


def test_normalize_telegram_update_success() -> None:
    subscription = telegram_subscription()
    update = build_telegram_update()
    payload = normalize_telegram_update(subscription, update)
    assert isinstance(payload, ListenerDispatchPayload)
    assert payload.message.text == "hi"
    assert payload.message.message_id == "55"
    assert payload.message.chat_type == "private"
    assert payload.message.chat_id == "123"
    assert payload.message.user_id == "456"
    assert payload.message.username == "Alex"
    assert payload.reply_target == {"chat_id": "123"}
    assert payload.metadata["node_name"] == subscription.node_name
    assert payload.dedupe_key == "telegram:10"


def test_normalize_filters_by_update_type() -> None:
    subscription = telegram_subscription(allowed_updates=["message"])
    update = {"update_id": 20, "inline_query": {"id": "iq"}, "message": {}}
    assert normalize_telegram_update(subscription, update) is None


def test_normalize_filters_by_chat_type() -> None:
    subscription = telegram_subscription(allowed_chat_types=["private"])
    update = {
        "update_id": 30,
        "message": {"chat": {"id": 1, "type": "group"}, "from": {"id": 2}},
    }
    assert normalize_telegram_update(subscription, update) is None


def test_normalize_requires_int_update_id() -> None:
    subscription = telegram_subscription()
    update = {"update_id": "x", "message": {"chat": {}, "from": {}}}
    assert normalize_telegram_update(subscription, update) is None


def test_normalize_allows_non_mapping_update_payload() -> None:
    subscription = telegram_subscription(allowed_chat_types=[])
    update = {"update_id": 41, "message": "not-a-dict"}
    payload = normalize_telegram_update(subscription, update)

    assert payload is not None
    assert payload.message.message_id is None
    assert payload.message.chat_id is None


def test_normalize_non_mapping_payload_branch_with_patched_extract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subscription = telegram_subscription(
        allowed_updates=["message"], allowed_chat_types=[]
    )
    monkeypatch.setattr(
        telegram_module,
        "detect_telegram_update_type",
        lambda payload: "message",
    )
    monkeypatch.setattr(
        telegram_module,
        "extract_telegram_update_details",
        lambda payload, update_type: ({}, {}, {}, ""),
    )
    payload = normalize_telegram_update(
        subscription, {"update_id": 42, "message": "bad"}
    )

    assert payload is not None
    assert payload.message.message_id is None


def test_normalize_leaves_message_id_empty_when_value_is_none() -> None:
    subscription = telegram_subscription()
    update = build_telegram_update(
        message={
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "first_name": "Alex"},
            "text": "hi",
            "message_id": None,
        }
    )
    payload = normalize_telegram_update(subscription, update)

    assert payload is not None
    assert payload.message.message_id is None


def test_normalize_none_message_id_branch_with_patched_extract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subscription = telegram_subscription(allowed_updates=["message"])
    monkeypatch.setattr(
        telegram_module,
        "detect_telegram_update_type",
        lambda payload: "message",
    )
    monkeypatch.setattr(
        telegram_module,
        "extract_telegram_update_details",
        lambda payload, update_type: (
            {},
            {"id": 123, "type": "private"},
            {"id": 456},
            "text",
        ),
    )
    payload = normalize_telegram_update(
        subscription,
        {"update_id": 43, "message": {"message_id": None}},
    )

    assert payload is not None
    assert payload.message.message_id is None


class StubPollingClient:
    def __init__(self, updates: list[dict[str, Any]]) -> None:
        self.updates = updates
        self.kwargs: dict[str, Any] = {}

    async def get_updates(
        self,
        *,
        token: str,
        offset: int | None,
        timeout: int,
        allowed_updates: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        self.kwargs = {
            "token": token,
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": allowed_updates,
            "limit": limit,
        }
        return self.updates


@pytest.mark.asyncio
async def test_poll_once_dispatches_and_saves_cursor() -> None:
    update = build_telegram_update()
    repository = TelegramRecordingRepository()
    adapter = TelegramPollingAdapter(
        repository=repository,
        subscription=telegram_subscription(
            poll_timeout_seconds=7,
            allowed_updates=["message"],
            max_batch_size=5,
        ),
        runtime_id="runtime",
        client=StubPollingClient([update]),
    )
    offset = await adapter.poll_once(token="token", offset=None)
    assert offset == 11
    assert repository.dispatched
    assert repository.saved[-1].telegram_offset == 11
    assert adapter._status == "healthy"


@pytest.mark.asyncio
async def test_poll_once_skips_updates_missing_id() -> None:
    updates = [build_telegram_update(update_id=None)]
    repository = TelegramRecordingRepository()
    adapter = TelegramPollingAdapter(
        repository=repository,
        subscription=telegram_subscription(),
        runtime_id="runtime",
        client=StubPollingClient(updates),
    )
    offset = await adapter.poll_once(token="token", offset=None)
    assert offset is None
    assert not repository.saved
    assert not repository.dispatched


@pytest.mark.asyncio
async def test_poll_once_filters_unallowed_updates_but_advances_cursor() -> None:
    inline_update = {
        "update_id": 99,
        "inline_query": {"id": "q"},
    }
    repository = TelegramRecordingRepository()
    adapter = TelegramPollingAdapter(
        repository=repository,
        subscription=telegram_subscription(allowed_updates=["message"]),
        runtime_id="runtime",
        client=StubPollingClient([inline_update]),
    )
    offset = await adapter.poll_once(token="token", offset=0)
    assert offset == 100
    assert repository.saved[-1].telegram_offset == 100
    assert not repository.dispatched


@pytest.mark.asyncio
async def test_run_clears_detail_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = TelegramRecordingRepository()
    adapter = TelegramPollingAdapter(
        repository=repository,
        subscription=telegram_subscription(token="token"),
        runtime_id="runtime",
        client=StubPollingClient([]),
    )
    adapter._detail = "stale"
    stop_event = asyncio.Event()

    async def fake_poll_once(
        self: TelegramPollingAdapter,
        *,
        token: str,
        offset: int | None,
    ) -> int | None:
        del self, token, offset
        stop_event.set()
        return 44

    monkeypatch.setattr(TelegramPollingAdapter, "poll_once", fake_poll_once)
    await adapter.run(stop_event)

    assert adapter._detail is None


def test_health_snapshot_reports_adapter_state() -> None:
    repository = TelegramRecordingRepository()
    adapter = TelegramPollingAdapter(
        repository=repository,
        subscription=telegram_subscription(token="token"),
        runtime_id="runtime",
        client=StubPollingClient([]),
    )

    health = adapter.health()

    assert health.platform is ListenerPlatform.TELEGRAM
    assert health.runtime_id == "runtime"
