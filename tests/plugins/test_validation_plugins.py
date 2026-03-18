"""Integration tests for the WeCom and Lark validation plugins."""

from __future__ import annotations
import asyncio
import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4
import pytest
from orcheo.graph.builder import build_graph
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
from orcheo.graph.ingestion.summary import summarise_graph_index, summarise_state_graph
from orcheo.listeners.compiler import compile_listener_subscriptions
from orcheo.listeners.models import ListenerSubscription
from orcheo.listeners.registry import listener_registry
from orcheo.nodes.registry import registry
from orcheo.plugins import load_enabled_plugins, reset_plugin_loader_for_tests
from orcheo.plugins.manager import PluginManager


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "packages" / "plugins"
LARK_PLUGIN_SRC = PLUGIN_ROOT / "lark_listener" / "src"
WECOM_PLUGIN_SRC = PLUGIN_ROOT / "wecom_listener" / "src"
TEMPLATE_SCRIPT = (
    REPO_ROOT
    / "apps"
    / "canvas"
    / "src"
    / "features"
    / "workflow"
    / "data"
    / "templates"
    / "assets"
    / "wecom-lark-shared-listener"
    / "workflow.py"
)


def _set_plugin_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins"
    cache_dir = tmp_path / "cache"
    config_dir = tmp_path / "config"
    plugin_dir.mkdir()
    cache_dir.mkdir()
    config_dir.mkdir()
    monkeypatch.setenv("ORCHEO_PLUGIN_DIR", str(plugin_dir))
    monkeypatch.setenv("ORCHEO_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("ORCHEO_CONFIG_DIR", str(config_dir))


def _load_plugins() -> None:
    reset_plugin_loader_for_tests()
    load_enabled_plugins(force=True)


class RecordingListenerRepository:
    """Repository stub that records dispatched listener payloads."""

    def __init__(self) -> None:
        self.events: list[tuple[object, object]] = []

    async def dispatch_listener_event(
        self, subscription_id: object, payload: object
    ) -> object:
        self.events.append((subscription_id, payload))
        return {"subscription_id": str(subscription_id)}


def _load_lark_plugin_module() -> ModuleType:
    module_name = "test_orcheo_plugin_lark_listener"
    module_path = LARK_PLUGIN_SRC / "orcheo_plugin_lark_listener" / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _load_wecom_plugin_module() -> ModuleType:
    module_name = "test_orcheo_plugin_wecom_listener"
    module_path = WECOM_PLUGIN_SRC / "orcheo_plugin_wecom_listener" / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def test_wecom_and_lark_plugins_coexist_and_compile_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Both validation plugins should load and compile from the shipped template."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    manager.install(str(PLUGIN_ROOT / "wecom_listener"))
    manager.install(str(PLUGIN_ROOT / "lark_listener"))

    _load_plugins()

    assert registry.get_node("WeComListenerPluginNode") is not None
    assert registry.get_node("LarkListenerPluginNode") is not None
    assert listener_registry.resolve("wecom") is not None
    assert listener_registry.resolve("lark") is not None

    graph = build_graph(
        {
            "format": LANGGRAPH_SCRIPT_FORMAT,
            "source": TEMPLATE_SCRIPT.read_text(encoding="utf-8"),
            "entrypoint": "orcheo_workflow",
        }
    )
    summary = summarise_state_graph(graph)
    index = summarise_graph_index(graph)
    subscriptions = compile_listener_subscriptions(
        uuid4(),
        uuid4(),
        {"index": index},
    )
    nodes_by_name = {node["name"]: node for node in summary["nodes"]}
    summary_edges = set(summary["edges"])
    start_conditional = next(
        (
            edge
            for edge in summary["conditional_edges"]
            if edge["source"] in {"START", "__start__"}
        ),
        None,
    )

    assert {item["type"] for item in index["listeners"]} == {
        "WeComListenerPluginNode",
        "LarkListenerPluginNode",
    }
    assert {subscription.platform for subscription in subscriptions} == {
        "wecom",
        "lark",
    }
    assert ("START", "wecom_listener") not in summary_edges
    assert ("START", "lark_listener") not in summary_edges
    assert start_conditional is not None
    assert start_conditional["mapping"] == {
        "wecom": "wecom_listener",
        "lark": "lark_listener",
    }
    assert nodes_by_name["agent_reply"]["type"] == "AgentNode"
    assert nodes_by_name["extract_reply"]["type"] == "AgentReplyExtractorNode"
    assert nodes_by_name["ws_reply_wecom"]["type"] == "WeComWsReplyNode"
    assert nodes_by_name["ws_reply_wecom"]["message"] == (
        "{{results.extract_reply.agent_reply}}"
    )
    assert nodes_by_name["ws_reply_wecom"]["raw_event"] == (
        "{{results.wecom_listener.raw_event}}"
    )
    assert nodes_by_name["get_lark_tenant_token"]["type"] == "HttpRequestNode"
    assert nodes_by_name["send_lark"]["type"] == "LarkSendMessageNode"
    assert nodes_by_name["send_lark"]["receive_id"] == (
        "{{results.lark_listener.reply_target.chat_id}}"
    )
    assert nodes_by_name["send_lark"]["reply_to_message_id"] == (
        "{{results.lark_listener.reply_target.message_id}}"
    )
    assert nodes_by_name["send_lark"]["message"] == (
        "{{results.extract_reply.agent_reply}}"
    )


@pytest.mark.asyncio()
async def test_wecom_plugin_dispatches_normalized_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The WeCom validation adapter should dispatch the shared payload contract."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    manager.install(str(PLUGIN_ROOT / "wecom_listener"))

    _load_plugins()

    subscriptions = compile_listener_subscriptions(
        uuid4(),
        uuid4(),
        {
            "index": {
                "listeners": [
                    {
                        "node_name": "wecom_listener",
                        "platform": "wecom",
                        "bot_id": "aib-test-bot",
                        "bot_secret": "test-secret",
                        "test_events": [
                            {
                                "text": "hello from wecom",
                                "to_user": "user-123",
                            }
                        ],
                    }
                ]
            }
        },
    )
    subscription = subscriptions[0]
    repository = RecordingListenerRepository()
    adapter = listener_registry.build_adapter(
        "wecom",
        repository=repository,
        subscription=subscription,
        runtime_id="wecom-runtime",
    )
    stop_event = asyncio.Event()
    task = asyncio.create_task(adapter.run(stop_event))
    await asyncio.sleep(0)
    stop_event.set()
    await task

    assert len(repository.events) == 1
    _subscription_id, payload = repository.events[0]
    assert payload.platform == "wecom"
    assert payload.message.text == "hello from wecom"
    assert payload.reply_target["to_user"] == "user-123"
    assert "corp_id" not in payload.reply_target
    assert adapter.health().status == "stopped"

    uninstall_impact = manager.uninstall("orcheo-plugin-wecom-listener")
    assert uninstall_impact.restart_required is True
    assert manager.list_plugins() == []


@pytest.mark.asyncio()
async def test_wecom_plugin_uses_websocket_mode_without_fixture_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The adapter should switch to WebSocket long-connection mode by default."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    manager.install(str(PLUGIN_ROOT / "wecom_listener"))

    _load_plugins()

    subscriptions = compile_listener_subscriptions(
        uuid4(),
        uuid4(),
        {
            "index": {
                "listeners": [
                    {
                        "node_name": "wecom_listener",
                        "platform": "wecom",
                        "bot_id": "aib-test-bot",
                        "bot_secret": "test-secret",
                    }
                ]
            }
        },
    )
    repository = RecordingListenerRepository()
    adapter = listener_registry.build_adapter(
        "wecom",
        repository=repository,
        subscription=subscriptions[0],
        runtime_id="wecom-runtime",
    )

    entered_ws_mode = asyncio.Event()

    async def fake_ws_mode(self, stop_event: asyncio.Event) -> None:
        self._status = "healthy"
        self._detail = "using websocket mode"
        entered_ws_mode.set()
        await stop_event.wait()
        self._status = "stopped"

    monkeypatch.setattr(
        type(adapter),
        "_run_websocket_connection",
        fake_ws_mode,
    )

    stop_event = asyncio.Event()
    task = asyncio.create_task(adapter.run(stop_event))
    await asyncio.wait_for(entered_ws_mode.wait(), timeout=1)
    stop_event.set()
    await task

    assert repository.events == []
    assert adapter.health().status == "stopped"


@pytest.mark.asyncio()
async def test_wecom_plugin_websocket_mode_blocks_when_config_missing() -> None:
    """The adapter should report blocked when bot_id or bot_secret is missing."""
    wecom_plugin = _load_wecom_plugin_module()
    subscription = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="wecom_listener",
        platform="wecom",
        bot_identity_key="wecom:primary",
        config={
            "bot_id": "",
            "bot_secret": "test-secret",
        },
    )
    repository = RecordingListenerRepository()
    adapter = wecom_plugin.WeComListenerAdapter(
        repository=repository,
        subscription=subscription,
        runtime_id="wecom-runtime",
    )

    stop_event = asyncio.Event()
    task = asyncio.create_task(adapter.run(stop_event))
    await asyncio.sleep(0)
    health = adapter.health()
    assert health.status == "error"
    assert health.detail is not None
    assert "bot_id" in health.detail
    assert "blocked:" in health.detail
    assert repository.events == []

    stop_event.set()
    await task
    assert adapter.health().status == "stopped"


def test_wecom_ws_event_normalization() -> None:
    """WebSocket frames should normalize into the shared listener payload."""
    wecom_plugin = _load_wecom_plugin_module()

    subscription = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="wecom_listener",
        platform="wecom",
        bot_identity_key="wecom:primary",
        config={
            "bot_id": "aib-test-bot",
            "bot_secret": "test-secret",
        },
    )

    frame = {
        "msgtype": "text",
        "body": {
            "from": {"user_id": "user-789"},
            "chat_id": "chat-abc",
            "msg_id": "msg-001",
            "text": {"content": "hello from websocket"},
        },
    }
    payload = wecom_plugin.normalize_wecom_ws_event(subscription, frame)
    assert payload is not None
    assert payload.platform == "wecom"
    assert payload.event_type == "text"
    assert payload.message.text == "hello from websocket"
    assert payload.message.user_id == "user-789"
    assert payload.message.message_id == "msg-001"
    assert payload.message.chat_id == "chat-abc"
    assert payload.message.chat_type == "group"
    assert "corp_id" not in payload.reply_target
    assert payload.reply_target["chat_id"] == "chat-abc"
    assert payload.reply_target["to_user"] is None
    assert payload.metadata["transport"] == "websocket"


def test_wecom_ws_event_normalization_private_message() -> None:
    """Private messages should set to_user instead of chat_id in reply_target."""
    wecom_plugin = _load_wecom_plugin_module()

    subscription = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="wecom_listener",
        platform="wecom",
        bot_identity_key="wecom:primary",
        config={},
    )

    frame = {
        "msgtype": "text",
        "body": {
            "from": {"user_id": "user-789"},
            "msg_id": "msg-002",
            "text": {"content": "private hello"},
        },
    }
    payload = wecom_plugin.normalize_wecom_ws_event(subscription, frame)
    assert payload is not None
    assert payload.message.chat_type == "private"
    assert payload.reply_target["to_user"] == "user-789"
    assert payload.reply_target["chat_id"] is None


def test_wecom_ws_event_normalization_image_and_file() -> None:
    """Image and file frames should produce text previews."""
    wecom_plugin = _load_wecom_plugin_module()

    subscription = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="wecom_listener",
        platform="wecom",
        bot_identity_key="wecom:primary",
        config={},
    )

    image_frame = {
        "msgtype": "image",
        "body": {
            "from": {"user_id": "user-1"},
            "image": {"url": "https://example.com/img.jpg"},
        },
    }
    payload = wecom_plugin.normalize_wecom_ws_event(subscription, image_frame)
    assert payload is not None
    assert payload.message.text == "[Image]"

    file_frame = {
        "msgtype": "file",
        "body": {
            "from": {"user_id": "user-1"},
            "file": {"file_name": "report.pdf"},
        },
    }
    payload = wecom_plugin.normalize_wecom_ws_event(subscription, file_frame)
    assert payload is not None
    assert payload.message.text == "[File] report.pdf"


def _prepare_wecom_websocket_mock(
    *,
    monkeypatch: pytest.MonkeyPatch,
    wecom_plugin: ModuleType,
    connected_loops: list[asyncio.AbstractEventLoop],
    first_loop_ref: list[asyncio.AbstractEventLoop | None],
) -> None:
    class FakeWSClient:
        def __init__(
            self, *, bot_id: str, secret: str, max_reconnect_attempts: int = 0
        ) -> None:
            self.bot_id = bot_id
            self.secret = secret
            self._handlers: dict[str, object] = {}

        def on(self, event_type: str, handler: object) -> None:
            self._handlers[event_type] = handler

        async def connect(self) -> None:
            running_loop = asyncio.get_running_loop()
            connected_loops.append(running_loop)
            if first_loop_ref[0] is None:
                first_loop_ref[0] = running_loop
            elif running_loop is not first_loop_ref[0]:
                raise RuntimeError("WeCom client was bound to a different loop.")
            handler = self._handlers.get("message.text")
            if handler is not None:
                running_loop.call_soon(
                    handler,
                    {
                        "msgtype": "text",
                        "body": {
                            "from": {"user_id": f"user-{self.bot_id}"},
                            "msg_id": f"msg-{self.bot_id}",
                            "text": {"content": f"hello from {self.bot_id}"},
                        },
                    },
                )

        async def disconnect(self) -> None:
            return None

    sdk_module = ModuleType("wecom_aibot_sdk")
    sdk_module.WSClient = FakeWSClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "wecom_aibot_sdk", sdk_module)
    monkeypatch.setattr(
        wecom_plugin,
        "get_wecom_long_connection_block_reason",
        lambda _config: None,
    )


@pytest.mark.asyncio()
async def test_wecom_plugin_websocket_mode_shares_one_sdk_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple WebSocket-mode adapters should reuse one SDK loop."""
    wecom_plugin = _load_wecom_plugin_module()
    connected_loops: list[asyncio.AbstractEventLoop] = []
    first_loop_ref: list[asyncio.AbstractEventLoop | None] = [None]

    _prepare_wecom_websocket_mock(
        monkeypatch=monkeypatch,
        wecom_plugin=wecom_plugin,
        connected_loops=connected_loops,
        first_loop_ref=first_loop_ref,
    )

    subscriptions = [
        ListenerSubscription(
            workflow_id=uuid4(),
            workflow_version_id=uuid4(),
            node_name=f"wecom_listener_{index}",
            platform="wecom",
            bot_identity_key=f"wecom:{index}",
            config={
                "bot_id": f"bot-{index}",
                "bot_secret": f"secret-{index}",
            },
        )
        for index in range(2)
    ]
    repositories = [RecordingListenerRepository(), RecordingListenerRepository()]
    adapters = [
        wecom_plugin.WeComListenerAdapter(
            repository=repository,
            subscription=subscription,
            runtime_id=f"runtime-{index}",
        )
        for index, (repository, subscription) in enumerate(
            zip(repositories, subscriptions, strict=True)
        )
    ]
    stop_events = [asyncio.Event(), asyncio.Event()]
    tasks: list[asyncio.Task[None]] = []

    try:
        tasks.append(asyncio.create_task(adapters[0].run(stop_events[0])))
        for _ in range(50):
            if repositories[0].events:
                break
            await asyncio.sleep(0.05)
        assert repositories[0].events

        tasks.append(asyncio.create_task(adapters[1].run(stop_events[1])))
        for _ in range(50):
            if repositories[1].events:
                break
            await asyncio.sleep(0.05)
        assert repositories[1].events
    finally:
        for stop_event in stop_events:
            stop_event.set()
        await asyncio.gather(*tasks)
        wecom_plugin._SHARED_WECOM_SDK_LOOP.shutdown()

    assert len(connected_loops) == 2
    assert len(set(connected_loops)) == 1
    assert repositories[0].events[0][1].message.text == "hello from bot-0"
    assert repositories[1].events[0][1].message.text == "hello from bot-1"
    assert adapters[0].health().status == "stopped"
    assert adapters[1].health().status == "stopped"


@pytest.mark.asyncio()
async def test_wecom_ws_reply_node_sends_via_client() -> None:
    """WeComWsReplyNode should call client.reply() with the correct body."""
    wecom_plugin = _load_wecom_plugin_module()

    reply_calls: list[tuple[object, object]] = []

    class FakeClient:
        async def reply(self, frame: object, body: object) -> None:
            reply_calls.append((frame, body))

    loop = asyncio.get_running_loop()
    sub_id = str(uuid4())
    wecom_plugin.register_wecom_client(sub_id, FakeClient(), loop)

    try:
        node = wecom_plugin.WeComWsReplyNode(
            name="test_reply",
            message="Hello from agent",
            raw_event={"headers": {"req_id": "req-001"}},
            subscription_id=sub_id,
        )
        result = await node.run({}, {})
        assert result == {"sent": True}
        assert len(reply_calls) == 1
        frame_arg, body_arg = reply_calls[0]
        assert frame_arg == {"headers": {"req_id": "req-001"}}
        assert body_arg["msgtype"] == "stream"
        assert body_arg["stream"]["content"] == "Hello from agent"
        assert body_arg["stream"]["finish"] is True
        assert str(body_arg["stream"]["id"]).startswith("orcheo-")
    finally:
        wecom_plugin.deregister_wecom_client(sub_id)


@pytest.mark.asyncio()
async def test_wecom_ws_reply_node_relays_via_backend_when_no_local_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WeComWsReplyNode should HTTP-relay through the backend when no local client."""
    wecom_plugin = _load_wecom_plugin_module()

    monkeypatch.setenv("ORCHEO_BACKEND_INTERNAL_URL", "http://test-backend:9999")

    import httpx

    captured_requests: list[httpx.Request] = []

    async def mock_send(
        self: object, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"sent": True})

    monkeypatch.setattr(httpx.AsyncClient, "send", mock_send)

    node = wecom_plugin.WeComWsReplyNode(
        name="test_reply",
        message="Hello via relay",
        raw_event={"headers": {"req_id": "req-002"}},
        subscription_id="nonexistent-sub-id",
    )
    result = await node.run({}, {})
    assert result == {"sent": True}
    assert len(captured_requests) == 1
    assert "/api/internal/listeners/wecom/reply" in str(captured_requests[0].url)
    assert b"Hello via relay" in captured_requests[0].content


@pytest.mark.asyncio()
async def test_lark_plugin_update_disable_and_uninstall(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The Lark validation plugin should support lifecycle operations."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    fixture_path = tmp_path / "lark_listener"
    shutil.copytree(PLUGIN_ROOT / "lark_listener", fixture_path)

    manager.install(str(fixture_path))
    _load_plugins()
    initial_registration = listener_registry.resolve("lark")
    assert initial_registration is not None

    module_path = fixture_path / "src" / "orcheo_plugin_lark_listener" / "__init__.py"
    module_path.write_text(
        module_path.read_text(encoding="utf-8").replace(
            '"hello from lark"',
            '"hello from lark v2"',
        ),
        encoding="utf-8",
    )
    pyproject_path = fixture_path / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text(encoding="utf-8").replace(
            'version = "0.1.0"',
            'version = "0.2.0"',
        ),
        encoding="utf-8",
    )

    update_result = manager.update("orcheo-plugin-lark-listener")
    assert update_result["impact"].restart_required is True

    _load_plugins()
    subscriptions = compile_listener_subscriptions(
        uuid4(),
        uuid4(),
        {
            "index": {
                "listeners": [
                    {
                        "node_name": "lark_listener",
                        "platform": "lark",
                        "app_id": "app-123",
                        "app_secret": "[[lark_app_secret]]",
                        "test_events": [
                            {
                                "text": "hello from lark v2",
                                "open_id": "lark-user",
                                "chat_id": "lark-room",
                            }
                        ],
                    }
                ]
            }
        },
    )
    repository = RecordingListenerRepository()
    adapter = listener_registry.build_adapter(
        "lark",
        repository=repository,
        subscription=subscriptions[0],
        runtime_id="lark-runtime",
    )
    stop_event = asyncio.Event()
    task = asyncio.create_task(adapter.run(stop_event))
    await asyncio.sleep(0)
    stop_event.set()
    await task

    _subscription_id, payload = repository.events[0]
    assert payload.message.text == "hello from lark v2"

    disable_impact = manager.set_enabled("orcheo-plugin-lark-listener", enabled=False)
    assert disable_impact.restart_required is True
    _load_plugins()
    assert listener_registry.resolve("lark") is None

    uninstall_impact = manager.uninstall("orcheo-plugin-lark-listener")
    assert uninstall_impact.restart_required is True


def test_lark_sdk_event_normalization_uses_official_payload_shape() -> None:
    """Official SDK events should normalize into the shared listener payload."""
    lark_plugin = _load_lark_plugin_module()

    class _SenderId:
        open_id = "ou_lark_user"

    class _Sender:
        sender_id = _SenderId()
        tenant_key = "tenant-key"

    class _Message:
        message_id = "om_xxx"
        chat_id = "oc_xxx"
        thread_id = "omt_xxx"
        chat_type = "group"
        message_type = "text"
        content = '{"text":"hello from official lark"}'

    class _EventData:
        sender = _Sender()
        message = _Message()

    class _Event:
        event = _EventData()

    subscription = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="lark_listener",
        platform="lark",
        bot_identity_key="lark:primary",
        config={"app_id": "cli_app_id"},
    )

    payload = lark_plugin.normalize_lark_sdk_event(subscription, _Event())
    assert payload.platform == "lark"
    assert payload.message.text == "hello from official lark"
    assert payload.message.user_id == "ou_lark_user"
    assert payload.message.message_id == "om_xxx"
    assert payload.reply_target["chat_id"] == "oc_xxx"
    assert payload.reply_target["open_id"] == "ou_lark_user"
    assert payload.reply_target["thread_id"] == "omt_xxx"
    assert payload.metadata["transport"] == "official-long-connection"


def test_lark_sdk_event_normalization_supports_legacy_message_schema() -> None:
    """Legacy p1/customized payloads should normalize into shared structure."""
    lark_plugin = _load_lark_plugin_module()

    class _Event:
        type = "message"
        uuid = "legacy-event-001"
        event = {
            "sender": {
                "sender_id": {"user_id": "ou_legacy_user"},
                "tenant_key": "tenant-key",
            },
            "message": {
                "chat_id": "oc_legacy_chat",
                "thread_id": "omt_legacy_thread",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"hello from legacy schema"}',
            },
        }

    subscription = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="lark_listener",
        platform="lark",
        bot_identity_key="lark:legacy",
        config={"app_id": "cli_app_id"},
    )

    payload = lark_plugin.normalize_lark_sdk_event(subscription, _Event())
    assert payload.platform == "lark"
    assert payload.event_type == "message"
    assert payload.message.text == "hello from legacy schema"
    assert payload.message.user_id == "ou_legacy_user"
    assert payload.message.message_id == "legacy-event-001"
    assert payload.reply_target["chat_id"] == "oc_legacy_chat"
    assert payload.reply_target["thread_id"] == "omt_legacy_thread"
    assert "message_id" not in payload.reply_target


def test_lark_long_connection_block_reason_detects_missing_message_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup validation should flag missing subscribed message events."""
    lark_plugin = _load_lark_plugin_module()

    def fake_request_json(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, str] | None = None,
        timeout: int = 15,
    ) -> dict[str, object]:
        _ = method, headers, body, timeout
        if url.endswith("/auth/v3/tenant_access_token/internal"):
            return {"code": 0, "tenant_access_token": "tenant-token"}
        if "/app_versions/" in url:
            return {"code": 0, "data": {"app_version": {"events": []}}}
        if "/open-apis/application/v6/applications/" in url:
            return {
                "code": 0,
                "data": {
                    "app": {
                        "online_version_id": "oav_test_version",
                        "callback_info": {"callback_type": "websocket"},
                    }
                },
            }
        raise AssertionError(f"Unexpected request URL: {url}")

    monkeypatch.setattr(lark_plugin, "_request_json", fake_request_json)

    reason = lark_plugin.get_lark_long_connection_block_reason(
        {
            "app_id": "cli_test_app",
            "app_secret": "secret",
            "domain": "https://open.larksuite.com",
        }
    )
    assert reason is not None
    assert "im.message.receive_v1" in reason


def test_lark_long_connection_block_reason_allows_message_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup validation should pass when the app subscribes to message events."""
    lark_plugin = _load_lark_plugin_module()

    def fake_request_json(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, str] | None = None,
        timeout: int = 15,
    ) -> dict[str, object]:
        _ = method, headers, body, timeout
        if url.endswith("/auth/v3/tenant_access_token/internal"):
            return {"code": 0, "tenant_access_token": "tenant-token"}
        if "/app_versions/" in url:
            return {
                "code": 0,
                "data": {"app_version": {"events": ["im.message.receive_v1"]}},
            }
        if "/open-apis/application/v6/applications/" in url:
            return {
                "code": 0,
                "data": {
                    "app": {
                        "online_version_id": "oav_test_version",
                        "callback_info": {"callback_type": "websocket"},
                    }
                },
            }
        raise AssertionError(f"Unexpected request URL: {url}")

    monkeypatch.setattr(lark_plugin, "_request_json", fake_request_json)

    reason = lark_plugin.get_lark_long_connection_block_reason(
        {
            "app_id": "cli_test_app",
            "app_secret": "secret",
            "domain": "https://open.larksuite.com",
        }
    )
    assert reason is None


def test_lark_long_connection_block_reason_accepts_localized_event_name_with_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Localized `events` labels should pass when event_infos include event_type."""
    lark_plugin = _load_lark_plugin_module()

    def fake_request_json(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, str] | None = None,
        timeout: int = 15,
    ) -> dict[str, object]:
        _ = method, headers, body, timeout
        if url.endswith("/auth/v3/tenant_access_token/internal"):
            return {"code": 0, "tenant_access_token": "tenant-token"}
        if "/app_versions/" in url:
            return {
                "code": 0,
                "data": {
                    "app_version": {
                        "events": ["接收消息"],
                        "event_infos": [
                            {
                                "event_name": "接收消息",
                                "event_type": "im.message.receive_v1",
                            }
                        ],
                    }
                },
            }
        if "/open-apis/application/v6/applications/" in url:
            return {
                "code": 0,
                "data": {
                    "app": {
                        "online_version_id": "oav_test_version",
                        "callback_info": {"callback_type": "websocket"},
                    }
                },
            }
        raise AssertionError(f"Unexpected request URL: {url}")

    monkeypatch.setattr(lark_plugin, "_request_json", fake_request_json)
    reason = lark_plugin.get_lark_long_connection_block_reason(
        {
            "app_id": "cli_test_app",
            "app_secret": "secret",
            "domain": "https://open.larksuite.com",
        }
    )
    assert reason is None


@pytest.mark.asyncio()
async def test_lark_plugin_official_mode_blocks_when_subscription_precheck_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter should report blocked when required Lark events are missing."""
    lark_plugin = _load_lark_plugin_module()
    subscription = ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="lark_listener",
        platform="lark",
        bot_identity_key="lark:primary",
        config={
            "app_id": "app-123",
            "app_secret": "secret-123",
            "domain": "https://open.larksuite.com",
        },
    )
    repository = RecordingListenerRepository()
    adapter = lark_plugin.LarkListenerAdapter(
        repository=repository,
        subscription=subscription,
        runtime_id="lark-runtime",
    )
    monkeypatch.setattr(
        lark_plugin,
        "get_lark_long_connection_block_reason",
        lambda _config: "missing im.message.receive_v1 subscription",
    )

    stop_event = asyncio.Event()
    task = asyncio.create_task(adapter.run(stop_event))
    await asyncio.sleep(0)
    health = adapter.health()
    assert health.status == "error"
    assert health.detail is not None
    assert "im.message.receive_v1" in health.detail
    assert "blocked:" in health.detail
    assert repository.events == []

    stop_event.set()
    await task
    assert adapter.health().status == "stopped"


@pytest.mark.asyncio()
async def test_lark_plugin_uses_official_mode_without_fixture_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The adapter should switch to official long-connection mode by default."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    manager.install(str(PLUGIN_ROOT / "lark_listener"))

    _load_plugins()

    subscriptions = compile_listener_subscriptions(
        uuid4(),
        uuid4(),
        {
            "index": {
                "listeners": [
                    {
                        "node_name": "lark_listener",
                        "platform": "lark",
                        "app_id": "app-123",
                        "app_secret": "[[lark_app_secret]]",
                    }
                ]
            }
        },
    )
    repository = RecordingListenerRepository()
    adapter = listener_registry.build_adapter(
        "lark",
        repository=repository,
        subscription=subscriptions[0],
        runtime_id="lark-runtime",
    )

    entered_official_mode = asyncio.Event()

    async def fake_official_mode(self, stop_event: asyncio.Event) -> None:
        self._status = "healthy"
        self._detail = "using official mode"
        entered_official_mode.set()
        await stop_event.wait()
        self._status = "stopped"

    monkeypatch.setattr(
        type(adapter),
        "_run_official_long_connection",
        fake_official_mode,
    )

    stop_event = asyncio.Event()
    task = asyncio.create_task(adapter.run(stop_event))
    await asyncio.wait_for(entered_official_mode.wait(), timeout=1)
    stop_event.set()
    await task

    assert repository.events == []
    assert adapter.health().status == "stopped"


class _LarkFakeDispatcher:
    def __init__(self, callback: object) -> None:
        self._callback = callback

    def do_without_validation(self, payload: bytes) -> None:
        app_id = payload.decode("utf-8")
        event = SimpleNamespace(
            event=SimpleNamespace(
                sender=SimpleNamespace(
                    sender_id=SimpleNamespace(open_id=f"ou_{app_id}"),
                    tenant_key="tenant-key",
                ),
                message=SimpleNamespace(
                    message_id=f"om_{app_id}",
                    chat_id=f"oc_{app_id}",
                    thread_id=f"omt_{app_id}",
                    chat_type="group",
                    message_type="text",
                    content=f'{{"text":"hello from {app_id}"}}',
                ),
            )
        )
        self._callback(event)


class _LarkFakeBuilder:
    def __init__(self) -> None:
        self._callback: object | None = None

    def _register(self, callback: object) -> _LarkFakeBuilder:
        self._callback = callback
        return self

    def register_p2_customized_event(
        self, _event_type: str, callback: object
    ) -> _LarkFakeBuilder:
        return self._register(callback)

    def register_p1_customized_event(
        self, _event_type: str, callback: object
    ) -> _LarkFakeBuilder:
        return self._register(callback)

    def register_p2_im_message_receive_v1(self, callback: object) -> _LarkFakeBuilder:
        return self._register(callback)

    def build(self) -> _LarkFakeDispatcher:
        assert self._callback is not None
        return _LarkFakeDispatcher(self._callback)


class _LarkFakeEventDispatcherHandler:
    @staticmethod
    def builder(_encrypt_key: str, _token: str) -> _LarkFakeBuilder:
        return _LarkFakeBuilder()


def _create_lark_fake_client_type(
    connected_loops: list[asyncio.AbstractEventLoop],
    first_loop_ref: list[asyncio.AbstractEventLoop | None],
) -> type:
    class _LarkFakeClient:
        def __init__(
            self,
            *,
            app_id: str,
            app_secret: str,
            event_handler: _LarkFakeDispatcher,
            domain: str,
            auto_reconnect: bool,
        ) -> None:
            self.app_id = app_id
            self.app_secret = app_secret
            self.event_handler = event_handler
            self.domain = domain
            self.auto_reconnect = auto_reconnect
            self._connected_loops = connected_loops
            self._first_loop_ref = first_loop_ref

        async def _connect(self) -> None:
            running_loop = asyncio.get_running_loop()
            self._connected_loops.append(running_loop)
            if self._first_loop_ref[0] is None:
                self._first_loop_ref[0] = running_loop
            elif running_loop is not self._first_loop_ref[0]:
                raise RuntimeError("Lark client was bound to a different loop.")
            running_loop.call_soon(
                self.event_handler.do_without_validation,
                self.app_id.encode("utf-8"),
            )

        async def _ping_loop(self) -> None:
            await asyncio.Future()

        async def _disconnect(self) -> None:
            return None

    return _LarkFakeClient


def _prepare_lark_official_sdk_mock(
    *,
    monkeypatch: pytest.MonkeyPatch,
    lark_plugin: ModuleType,
    connected_loops: list[asyncio.AbstractEventLoop],
    first_loop_ref: list[asyncio.AbstractEventLoop | None],
) -> None:
    lark_module = ModuleType("lark_oapi")
    event_module = ModuleType("lark_oapi.event")
    dispatcher_module = ModuleType("lark_oapi.event.dispatcher_handler")
    dispatcher_module.EventDispatcherHandler = _LarkFakeEventDispatcherHandler
    ws_module = ModuleType("lark_oapi.ws")
    ws_client_module = ModuleType("lark_oapi.ws.client")
    ws_client_module.Client = _create_lark_fake_client_type(
        connected_loops, first_loop_ref
    )
    ws_client_module.loop = None
    lark_module.event = event_module
    lark_module.ws = ws_module
    event_module.dispatcher_handler = dispatcher_module
    ws_module.client = ws_client_module

    monkeypatch.setitem(sys.modules, "lark_oapi", lark_module)
    monkeypatch.setitem(sys.modules, "lark_oapi.event", event_module)
    monkeypatch.setitem(
        sys.modules,
        "lark_oapi.event.dispatcher_handler",
        dispatcher_module,
    )
    monkeypatch.setitem(sys.modules, "lark_oapi.ws", ws_module)
    monkeypatch.setitem(sys.modules, "lark_oapi.ws.client", ws_client_module)
    monkeypatch.setattr(
        lark_plugin,
        "get_lark_long_connection_block_reason",
        lambda _config: None,
    )


@pytest.mark.asyncio()
async def test_lark_plugin_official_mode_shares_one_sdk_loop_for_multiple_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple official-mode adapters should reuse one SDK loop and dispatch."""
    lark_plugin = _load_lark_plugin_module()
    connected_loops: list[asyncio.AbstractEventLoop] = []
    first_loop_ref: list[asyncio.AbstractEventLoop | None] = [None]

    _prepare_lark_official_sdk_mock(
        monkeypatch=monkeypatch,
        lark_plugin=lark_plugin,
        connected_loops=connected_loops,
        first_loop_ref=first_loop_ref,
    )

    subscriptions = [
        ListenerSubscription(
            workflow_id=uuid4(),
            workflow_version_id=uuid4(),
            node_name=f"lark_listener_{index}",
            platform="lark",
            bot_identity_key=f"lark:{index}",
            config={
                "app_id": f"app-{index}",
                "app_secret": f"secret-{index}",
            },
        )
        for index in range(2)
    ]
    repositories = [RecordingListenerRepository(), RecordingListenerRepository()]
    adapters = [
        lark_plugin.LarkListenerAdapter(
            repository=repository,
            subscription=subscription,
            runtime_id=f"runtime-{index}",
        )
        for index, (repository, subscription) in enumerate(
            zip(repositories, subscriptions, strict=True)
        )
    ]
    stop_events = [asyncio.Event(), asyncio.Event()]
    tasks: list[asyncio.Task[None]] = []

    try:
        tasks.append(asyncio.create_task(adapters[0].run(stop_events[0])))
        for _ in range(50):
            if repositories[0].events:
                break
            await asyncio.sleep(0.05)
        assert repositories[0].events

        tasks.append(asyncio.create_task(adapters[1].run(stop_events[1])))
        for _ in range(50):
            if repositories[1].events:
                break
            await asyncio.sleep(0.05)
        assert repositories[1].events
    finally:
        for stop_event in stop_events:
            stop_event.set()
        await asyncio.gather(*tasks)
        lark_plugin._SHARED_LARK_SDK_LOOP.shutdown()

    assert len(connected_loops) == 2
    assert len(set(connected_loops)) == 1
    assert repositories[0].events[0][1].message.text == "hello from app-0"
    assert repositories[1].events[0][1].message.text == "hello from app-1"
    assert adapters[0].health().status == "stopped"
    assert adapters[1].health().status == "stopped"
