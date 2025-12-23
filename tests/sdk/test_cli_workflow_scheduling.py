from __future__ import annotations
from types import SimpleNamespace
import pytest
from orcheo_sdk.cli.config import CLISettings
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.workflow.commands import scheduling


class _FakeConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, message: str) -> None:
        self.messages.append(message)


class _FakeContext:
    def __init__(self, state: CLIState) -> None:
        self._state = state

    def ensure_object(self, obj_type: type) -> CLIState:
        return self._state


def _make_state(*, offline: bool = False) -> CLIState:
    settings = CLISettings(
        api_url="http://api",
        service_token=None,
        profile="default",
        offline=offline,
    )
    return CLIState(
        settings=settings,
        client=SimpleNamespace(),
        cache=SimpleNamespace(),
        console=_FakeConsole(),
    )


def _context(state: CLIState) -> _FakeContext:
    return _FakeContext(state)


def test_schedule_workflow_requires_network() -> None:
    """Scheduling workflows raises when offline mode is enabled."""

    state = _make_state(offline=True)
    ctx = _context(state)

    with pytest.raises(CLIError, match="requires network connectivity"):
        scheduling.schedule_workflow(ctx, "wf-123")


def test_schedule_workflow_handles_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scheduling prints a yellow message when there is no cron trigger."""

    state = _make_state()
    ctx = _context(state)

    monkeypatch.setattr(
        scheduling,
        "schedule_workflow_cron",
        lambda *_args, **_kwargs: {
            "status": "noop",
            "message": "Nothing to schedule",
        },
    )

    scheduling.schedule_workflow(ctx, "wf-123")

    assert state.console.messages == ["[yellow]Nothing to schedule[/yellow]"]


def test_schedule_workflow_renders_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scheduling prints a success message and renders the cron config."""

    state = _make_state()
    ctx = _context(state)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        scheduling,
        "schedule_workflow_cron",
        lambda *_args, **_kwargs: {
            "status": "scheduled",
            "message": "Scheduled cron",
            "config": {"expression": "0 0 * * *"},
        },
    )

    def fake_render_json(
        console: object, payload: object, *, title: str | None = None
    ) -> None:
        captured["payload"] = payload
        captured["title"] = title

    monkeypatch.setattr(scheduling, "render_json", fake_render_json)

    scheduling.schedule_workflow(ctx, "wf-123")

    assert state.console.messages == ["[green]Scheduled cron[/green]"]
    assert captured["payload"] == {"expression": "0 0 * * *"}
    assert captured["title"] == "Cron trigger"


def test_unschedule_workflow_requires_network() -> None:
    """Unscheduling workflows raises when offline mode is enabled."""

    state = _make_state(offline=True)
    ctx = _context(state)

    with pytest.raises(CLIError, match="requires network connectivity"):
        scheduling.unschedule_workflow(ctx, "wf-123")


def test_unschedule_workflow_prints_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unscheduling workflows prints a green message."""

    state = _make_state()
    ctx = _context(state)

    monkeypatch.setattr(
        scheduling,
        "unschedule_workflow_cron",
        lambda *_args, **_kwargs: {"message": "Cron removed"},
    )

    scheduling.unschedule_workflow(ctx, "wf-123")

    assert state.console.messages == ["[green]Cron removed[/green]"]
