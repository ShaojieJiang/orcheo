"""Tests covering the high-level `run_workflow` CLI helper."""

from __future__ import annotations
from typing import Any
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.workflow import run_workflow
from tests.sdk.workflow_cli_test_utils import DummyCtx, make_state


def test_run_workflow_raises_on_failed_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = make_state()

    state.client.responses = {
        "/api/workflows/wf-1/versions": [
            {"id": "ver-1", "version": 1, "graph": {"nodes": []}}
        ]
    }

    async def fake_stream(
        state_arg: Any,
        workflow_id: str,
        graph_config: dict[str, Any],
        inputs: Any,
        triggered_by: str | None = None,
    ) -> str:
        assert state_arg is state
        assert workflow_id == "wf-1"
        assert graph_config == {"nodes": []}
        assert inputs == {}
        assert triggered_by == "cli"
        return "error"

    monkeypatch.setattr("orcheo_sdk.cli.workflow._stream_workflow_run", fake_stream)

    with pytest.raises(CLIError) as excinfo:
        run_workflow(DummyCtx(state), "wf-1")
    assert "Workflow execution failed" in str(excinfo.value)


def test_run_workflow_allows_successful_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = make_state()

    state.client.responses = {
        "/api/workflows/wf-1/versions": [
            {"id": "ver-1", "version": 1, "graph": {"nodes": []}}
        ]
    }

    async def fake_stream(
        state_arg: Any,
        workflow_id: str,
        graph_config: dict[str, Any],
        inputs: Any,
        triggered_by: str | None = None,
    ) -> str:
        assert state_arg is state
        assert workflow_id == "wf-1"
        assert graph_config == {"nodes": []}
        assert inputs == {}
        assert triggered_by == "cli"
        return "completed"

    monkeypatch.setattr("orcheo_sdk.cli.workflow._stream_workflow_run", fake_stream)

    run_workflow(DummyCtx(state), "wf-1")
