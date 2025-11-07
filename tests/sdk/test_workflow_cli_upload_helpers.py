"""Tests for workflow upload helpers related to LangGraph scripts."""

from __future__ import annotations
from pathlib import Path
from typing import Any
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.workflow import _upload_langgraph_script, upload_workflow
from tests.sdk.workflow_cli_test_utils import DummyCtx, StubClient, make_state


def test_upload_langgraph_script_fetch_failure() -> None:
    state = make_state()

    class FailingClient(StubClient):
        def get(self, url: str) -> Any:  # type: ignore[override]
            raise RuntimeError("boom")

    state.client = FailingClient()

    workflow_config = {"script": "print('hello')", "entrypoint": None}
    with pytest.raises(CLIError) as excinfo:
        _upload_langgraph_script(
            state,
            workflow_config,
            "wf-1",
            Path("demo.py"),
            None,
        )
    assert "Failed to fetch workflow" in str(excinfo.value)


def test_upload_langgraph_script_create_failure() -> None:
    state = make_state()

    class CreatingClient(StubClient):
        def post(self, url: str, **payload: Any) -> Any:  # type: ignore[override]
            if url.endswith("/api/workflows"):
                raise RuntimeError("cannot create")
            return {"version": 1}

    state.client = CreatingClient()

    workflow_config = {"script": "print('hello')", "entrypoint": None}
    with pytest.raises(CLIError) as excinfo:
        _upload_langgraph_script(
            state,
            workflow_config,
            None,
            Path("demo.py"),
            None,
        )
    assert "Failed to create workflow" in str(excinfo.value)


def test_upload_langgraph_script_rename_failure() -> None:
    state = make_state()

    class RenameFailingClient(StubClient):
        def get(self, url: str) -> Any:  # type: ignore[override]
            assert url.endswith("/api/workflows/wf-1")
            return {"id": "wf-1", "name": "existing"}

        def post(self, url: str, **payload: Any) -> Any:  # type: ignore[override]
            raise RuntimeError("cannot rename")

    state.client = RenameFailingClient()

    workflow_config = {"script": "print('hello')", "entrypoint": None}
    with pytest.raises(CLIError) as excinfo:
        _upload_langgraph_script(
            state,
            workflow_config,
            "wf-1",
            Path("demo.py"),
            "New Name",
        )
    assert "Failed to rename workflow 'wf-1'" in str(excinfo.value)


def test_upload_workflow_overrides_entrypoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = make_state()
    dummy_path = tmp_path / "workflow.py"
    dummy_path.write_text("print('hello')", encoding="utf-8")

    loaded_config = {
        "_type": "langgraph_script",
        "script": "print('hello')",
        "entrypoint": None,
    }

    captured_config: dict[str, Any] | None = None

    def fake_loader(path: Path) -> dict[str, Any]:
        assert path == dummy_path
        return dict(loaded_config)

    def fake_uploader(
        state_arg: Any,
        workflow_config: dict[str, Any],
        workflow_id: str | None,
        path: Path,
        name_override: str | None,
    ) -> dict[str, Any]:
        nonlocal captured_config
        captured_config = workflow_config
        assert workflow_id is None
        assert path == dummy_path
        assert name_override is None
        return {"id": "wf-123"}

    def fake_render(console: Any, data: Any, title: Any = None) -> None:
        state.console.messages.append(f"render:{data}")

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._load_workflow_from_python", fake_loader
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._upload_langgraph_script", fake_uploader
    )
    monkeypatch.setattr("orcheo_sdk.cli.workflow.render_json", fake_render)

    upload_workflow(
        DummyCtx(state),
        str(dummy_path),
        entrypoint="custom.entry",
    )

    assert captured_config is not None
    assert captured_config["entrypoint"] == "custom.entry"


def test_upload_workflow_rejects_directory_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = make_state()
    outside_file = tmp_path.parent / "outside.py"
    outside_file.write_text("print('hi')", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    with pytest.raises(CLIError) as excinfo:
        upload_workflow(DummyCtx(state), "../outside.py")

    assert "escapes the current working directory" in str(excinfo.value)
