"""Upload workflow command tests for cron sync branches in managing.py."""

from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import pytest
from orcheo_sdk.cli.config import CLISettings
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.workflow.commands import managing


class _FakeConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, message: str) -> None:
        self.messages.append(message)


class _FakeContext:
    def __init__(self, state: CLIState) -> None:
        self._state = state

    def ensure_object(self, _obj_type: type) -> CLIState:
        return self._state


def _make_state(*, offline: bool = False, human: bool = True) -> CLIState:
    settings = CLISettings(
        api_url="http://api",
        service_token=None,
        profile="default",
        offline=offline,
    )
    return CLIState(
        settings=settings,
        client=SimpleNamespace(),  # type: ignore[arg-type]
        cache=SimpleNamespace(),  # type: ignore[arg-type]
        console=_FakeConsole(),  # type: ignore[arg-type]
        human=human,
    )


def _context(state: CLIState) -> _FakeContext:
    return _FakeContext(state)


def test_upload_workflow_no_resolved_id_skips_cron_sync(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When upload returns no id and workflow_id is None, cron sync is skipped."""
    cron_sync_called: list[bool] = []

    monkeypatch.setattr(
        managing,
        "upload_workflow_data",
        lambda *_args, **_kwargs: {},  # no "id" key → resolved_id is None
    )
    monkeypatch.setattr(
        managing,
        "sync_cron_schedule_if_changed",
        lambda *_args, **_kwargs: cron_sync_called.append(True) or {},
    )
    monkeypatch.setattr(
        managing,
        "render_json",
        lambda *_args, **_kwargs: None,
    )

    state = _make_state()
    ctx = _context(state)
    py_file = tmp_path / "wf.py"
    py_file.write_text("# empty", encoding="utf-8")

    managing.upload_workflow(ctx, py_file)

    # Cron sync must not be invoked when resolved_id is falsy (branch 99->105)
    assert not cron_sync_called
    # identifier falls back to "workflow" when resolved_id is None
    assert any("workflow" in msg for msg in state.console.messages)


def test_upload_workflow_machine_mode_includes_cron_schedule_when_updated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Machine mode upload includes cron_schedule in output when cron was updated."""
    monkeypatch.setattr(
        managing,
        "upload_workflow_data",
        lambda *_args, **_kwargs: {"id": "wf-1", "name": "my-wf"},
    )
    monkeypatch.setattr(
        managing,
        "sync_cron_schedule_if_changed",
        lambda *_args, **_kwargs: {
            "status": "updated",
            "message": "Cron schedule updated for workflow 'wf-1'.",
            "config": {"expression": "0 * * * *"},
        },
    )
    printed: list[dict[str, object]] = []
    monkeypatch.setattr(managing, "print_json", lambda data: printed.append(data))

    state = _make_state(human=False)
    ctx = _context(state)
    py_file = tmp_path / "wf.py"
    py_file.write_text("# empty", encoding="utf-8")

    managing.upload_workflow(ctx, py_file)

    # Line 107: result["cron_schedule"] = cron_sync is set before print_json
    assert len(printed) == 1
    output = printed[0]
    assert output["id"] == "wf-1"
    assert "cron_schedule" in output
    assert output["cron_schedule"]["status"] == "updated"  # type: ignore[index]


def test_upload_workflow_human_mode_prints_cron_message_when_updated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Human mode upload prints cron update message and renders config."""
    monkeypatch.setattr(
        managing,
        "upload_workflow_data",
        lambda *_args, **_kwargs: {"id": "wf-1", "name": "my-wf"},
    )
    monkeypatch.setattr(
        managing,
        "sync_cron_schedule_if_changed",
        lambda *_args, **_kwargs: {
            "status": "updated",
            "message": "Cron schedule updated for workflow 'wf-1'.",
            "config": {"expression": "0 * * * *"},
        },
    )
    render_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        managing,
        "render_json",
        lambda _console, payload, *, title=None: render_calls.append(
            {"payload": payload, "title": title}
        ),
    )

    state = _make_state(human=True)
    ctx = _context(state)
    py_file = tmp_path / "wf.py"
    py_file.write_text("# empty", encoding="utf-8")

    managing.upload_workflow(ctx, py_file)

    # Line 116: cron message is printed in green
    cron_messages = [m for m in state.console.messages if "Cron schedule updated" in m]
    assert len(cron_messages) == 1
    assert "[green]" in cron_messages[0]

    # Line 117: cron config is rendered under "Cron trigger" title
    cron_renders = [c for c in render_calls if c.get("title") == "Cron trigger"]
    assert len(cron_renders) == 1
    assert cron_renders[0]["payload"] == {"expression": "0 * * * *"}


def test_upload_workflow_machine_mode_without_updated_cron_skips_schedule_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Machine upload should not inject cron_schedule unless status is updated."""

    monkeypatch.setattr(
        managing,
        "upload_workflow_data",
        lambda *_args, **_kwargs: {"id": "wf-1", "name": "my-wf"},
    )
    monkeypatch.setattr(
        managing,
        "sync_cron_schedule_if_changed",
        lambda *_args, **_kwargs: {"status": "unchanged"},
    )
    printed: list[dict[str, object]] = []
    monkeypatch.setattr(managing, "print_json", lambda data: printed.append(data))

    state = _make_state(human=False)
    ctx = _context(state)
    py_file = tmp_path / "wf.py"
    py_file.write_text("# empty", encoding="utf-8")

    managing.upload_workflow(ctx, py_file)

    assert len(printed) == 1
    assert "cron_schedule" not in printed[0]


def test_save_workflow_config_offline_raises_error() -> None:
    """Saving config should fail immediately in offline mode."""

    state = _make_state(offline=True)
    ctx = _context(state)

    with pytest.raises(CLIError, match="requires network connectivity"):
        managing.save_workflow_config(
            ctx, "wf-1", config='{"tags": ["x"]}', clear=False
        )


def test_save_workflow_config_clear_with_config_raises_error() -> None:
    """--clear and --config are mutually exclusive."""

    state = _make_state()
    ctx = _context(state)

    with pytest.raises(CLIError, match="Use either --clear or --config/--config-file"):
        managing.save_workflow_config(
            ctx,
            "wf-1",
            config='{"tags": ["x"]}',
            clear=True,
        )


def test_save_workflow_config_machine_mode_prints_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Machine mode save-config should print raw result JSON."""

    monkeypatch.setattr(
        managing,
        "save_workflow_runnable_config_data",
        lambda *_args, **_kwargs: {"id": "ver-1", "version": 1},
    )
    printed: list[dict[str, object]] = []
    monkeypatch.setattr(managing, "print_json", lambda data: printed.append(data))

    state = _make_state(human=False)
    ctx = _context(state)
    managing.save_workflow_config(ctx, "wf-1", config='{"tags": ["x"]}', clear=False)

    assert printed == [{"id": "ver-1", "version": 1}]


def test_download_workflow_machine_mode_stdout_prints_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Machine download without output path should emit payload JSON."""

    monkeypatch.setattr(
        managing,
        "load_with_cache",
        lambda *_args, **_kwargs: (
            {"content": "print('hello')", "version": 1},
            False,
            False,
        ),
    )
    printed: list[dict[str, object]] = []
    monkeypatch.setattr(managing, "print_json", lambda data: printed.append(data))

    state = _make_state(human=False)
    ctx = _context(state)
    managing.download_workflow(ctx, "wf-1")

    assert printed == [{"content": "print('hello')", "version": 1}]


def test_download_workflow_human_mode_output_path_prints_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Human download to a file should print a success message."""

    monkeypatch.setattr(
        managing,
        "load_with_cache",
        lambda *_args, **_kwargs: ({"content": "print('hello')"}, False, False),
    )

    state = _make_state(human=True)
    ctx = _context(state)
    output_file = tmp_path / "wf.py"

    managing.download_workflow(ctx, "wf-1", output_path=output_file)

    assert output_file.read_text(encoding="utf-8") == "print('hello')"
    assert any("Workflow downloaded to" in msg for msg in state.console.messages)
