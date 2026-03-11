"""Unit tests for ListenerRuntimeService covering all code paths."""

from __future__ import annotations
import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from orcheo.listeners import ListenerPlatform, ListenerSubscription
from orcheo_backend.app.listener_runtime import ListenerRuntimeStore
from orcheo_backend.app.listener_runtime_service import ListenerRuntimeService


def _make_subscription(platform: ListenerPlatform) -> ListenerSubscription:
    return ListenerSubscription(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        node_name="test_listener",
        platform=platform,
        bot_identity_key=f"{platform.value}:test-bot",
        config={"token": "plain-token"},
    )


def _make_service(
    runtime_id: str = "test-runtime",
    health_interval: float = 0.01,
) -> tuple[ListenerRuntimeService, MagicMock]:
    """Return a ListenerRuntimeService with its ListenerSupervisor mocked out."""
    repository = MagicMock()
    vault = MagicMock()
    runtime_store = ListenerRuntimeStore()

    supervisor = MagicMock()
    supervisor.serve = AsyncMock()
    supervisor.health = MagicMock(return_value=[])

    with patch(
        "orcheo_backend.app.listener_runtime_service.ListenerSupervisor",
        return_value=supervisor,
    ):
        service = ListenerRuntimeService(
            repository=repository,
            vault=vault,
            runtime_store=runtime_store,
            runtime_id=runtime_id,
            reconcile_interval_seconds=0.01,
            health_publish_interval_seconds=health_interval,
        )
    return service, supervisor


# ---------------------------------------------------------------------------
# runtime_id property (line 99)
# ---------------------------------------------------------------------------


def test_runtime_id_property() -> None:
    """runtime_id property returns the identifier given at construction time."""
    service, _ = _make_service(runtime_id="my-custom-runtime")
    assert service.runtime_id == "my-custom-runtime"


# ---------------------------------------------------------------------------
# start() idempotency (line 104)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_start_is_idempotent() -> None:
    """A second call to start() returns immediately without spawning new tasks."""

    async def _blocking_serve(stop_event: asyncio.Event) -> None:
        await asyncio.sleep(1000)

    service, supervisor = _make_service()
    supervisor.serve = _blocking_serve

    await service.start()
    serve_task_after_first = service._serve_task
    health_task_after_first = service._health_task

    # Second start must not create new tasks.
    await service.start()
    assert service._serve_task is serve_task_after_first
    assert service._health_task is health_task_after_first

    service._stop_event.set()
    await service.stop()


# ---------------------------------------------------------------------------
# stop() swallows CancelledError from externally-cancelled tasks (lines 123-124)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_stop_swallows_cancelled_error_from_tasks() -> None:
    """stop() must not propagate CancelledError from tasks cancelled externally."""
    service, _ = _make_service()

    async def _never_returns() -> None:
        await asyncio.sleep(1000)

    # Plant a pre-cancelled task directly without calling start().
    task: asyncio.Task[None] = asyncio.create_task(_never_returns())
    task.cancel()
    # Yield so the cancellation is processed before stop() awaits the task.
    await asyncio.sleep(0.01)

    service._serve_task = task
    service._health_task = None
    service._stop_event.set()

    await service.stop()  # must not raise

    assert service._serve_task is None
    assert service._health_task is None


# ---------------------------------------------------------------------------
# _build_adapter – Discord (lines 141-146)
# ---------------------------------------------------------------------------


def test_build_adapter_discord(monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_adapter instantiates a DiscordGatewayAdapter for DISCORD subscriptions."""
    mod = importlib.import_module("orcheo_backend.app.listener_runtime_service")

    mock_adapter = MagicMock()
    mock_cls = MagicMock(return_value=mock_adapter)
    monkeypatch.setattr(mod, "DiscordGatewayAdapter", mock_cls)

    service, _ = _make_service()
    adapter = service._build_adapter(_make_subscription(ListenerPlatform.DISCORD))

    assert adapter is mock_adapter
    mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# _build_adapter – QQ (lines 147-152)
# ---------------------------------------------------------------------------


def test_build_adapter_qq(monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_adapter instantiates a QQGatewayAdapter for QQ subscriptions."""
    mod = importlib.import_module("orcheo_backend.app.listener_runtime_service")

    mock_adapter = MagicMock()
    mock_cls = MagicMock(return_value=mock_adapter)
    monkeypatch.setattr(mod, "QQGatewayAdapter", mock_cls)

    service, _ = _make_service()
    adapter = service._build_adapter(_make_subscription(ListenerPlatform.QQ))

    assert adapter is mock_adapter
    mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# _build_adapter – unsupported platform (lines 153-154)
# ---------------------------------------------------------------------------


def test_build_adapter_unsupported_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_adapter raises ValueError when the platform is not recognised."""
    mod = importlib.import_module("orcheo_backend.app.listener_runtime_service")

    fake_resolved = MagicMock()
    fake_resolved.platform = "fax"
    monkeypatch.setattr(
        mod,
        "resolve_listener_subscription_credentials",
        lambda s, **k: fake_resolved,
    )

    service, _ = _make_service()
    with pytest.raises(ValueError, match="Unsupported listener platform"):
        service._build_adapter(_make_subscription(ListenerPlatform.TELEGRAM))


# ---------------------------------------------------------------------------
# _run_supervisor – CancelledError re-raised (line 159)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_run_supervisor_reraises_cancelled_error() -> None:
    """_run_supervisor re-raises CancelledError from the underlying supervisor."""
    service, supervisor = _make_service()
    supervisor.serve = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await service._run_supervisor()


# ---------------------------------------------------------------------------
# _run_supervisor – unexpected exception logged and re-raised (lines 161-163)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_run_supervisor_logs_and_reraises_exception() -> None:
    """_run_supervisor logs and re-raises unexpected exceptions from the supervisor."""
    service, supervisor = _make_service()
    supervisor.serve = AsyncMock(side_effect=RuntimeError("supervisor-crash"))

    with pytest.raises(RuntimeError, match="supervisor-crash"):
        await service._run_supervisor()


# ---------------------------------------------------------------------------
# _publish_health_loop – TimeoutError continue path (lines 174-175)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_health_loop_continues_on_timeout() -> None:
    """Health loop iterates on timeout and publishes a final snapshot on stop."""
    service, supervisor = _make_service(health_interval=0.01)

    health_calls: list[int] = []

    def _counting_health() -> list:
        health_calls.append(1)
        return []

    supervisor.health = _counting_health

    loop_task = asyncio.create_task(service._publish_health_loop())
    # Run for several timeout cycles, then stop.
    await asyncio.sleep(0.06)
    service._stop_event.set()
    await loop_task

    # At minimum: initial publish + one cycle + final publish after loop exit.
    assert len(health_calls) >= 2


# ---------------------------------------------------------------------------
# _publish_health_loop – CancelledError re-raised (line 177)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_health_loop_reraises_cancelled_error() -> None:
    """_publish_health_loop re-raises CancelledError when the task is cancelled."""
    service, _ = _make_service(health_interval=0.01)

    task = asyncio.create_task(service._publish_health_loop())
    await asyncio.sleep(0.01)  # let the loop start
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


# ---------------------------------------------------------------------------
# _publish_health_loop – unexpected exception logged and re-raised (lines 179-184)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_publish_health_loop_logs_and_reraises_exception() -> None:
    """_publish_health_loop logs and re-raises unexpected exceptions."""
    service, supervisor = _make_service(health_interval=0.01)
    supervisor.health = MagicMock(side_effect=RuntimeError("health-crash"))

    with pytest.raises(RuntimeError, match="health-crash"):
        await service._publish_health_loop()
