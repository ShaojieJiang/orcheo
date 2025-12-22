"""Tests covering the high-level `run_workflow` CLI helper."""

from __future__ import annotations
from typing import Any
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.workflow import evaluate_workflow, run_workflow
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
        runnable_config: Any | None = None,
        stored_runnable_config: Any | None = None,
    ) -> str:
        assert state_arg is state
        assert workflow_id == "wf-1"
        assert graph_config == {"nodes": []}
        assert inputs == {}
        assert triggered_by == "cli"
        assert runnable_config is None
        assert stored_runnable_config is None
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
        runnable_config: Any | None = None,
        stored_runnable_config: Any | None = None,
    ) -> str:
        assert state_arg is state
        assert workflow_id == "wf-1"
        assert graph_config == {"nodes": []}
        assert inputs == {}
        assert triggered_by == "cli"
        assert runnable_config is None
        assert stored_runnable_config is None
        return "completed"

    monkeypatch.setattr("orcheo_sdk.cli.workflow._stream_workflow_run", fake_stream)

    run_workflow(DummyCtx(state), "wf-1")


def test_evaluate_workflow_streams_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = make_state()

    state.client.responses = {
        "/api/workflows/wf-2/versions": [
            {"id": "ver-1", "version": 1, "graph": {"nodes": []}}
        ]
    }

    async def fake_stream(
        state_arg: Any,
        workflow_id: str,
        graph_config: dict[str, Any],
        inputs: Any,
        evaluation: Any,
        triggered_by: str | None = None,
        runnable_config: Any | None = None,
        stored_runnable_config: Any | None = None,
    ) -> str:
        assert state_arg is state
        assert workflow_id == "wf-2"
        assert graph_config == {"nodes": []}
        assert inputs == {}
        assert evaluation == {"dataset": {"cases": [{"inputs": {"a": 1}}]}}
        assert triggered_by == "cli"
        assert runnable_config is None
        assert stored_runnable_config is None
        return "completed"

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._stream_workflow_evaluation", fake_stream
    )

    evaluate_payload = '{"dataset": {"cases": [{"inputs": {"a": 1}}]}}'
    evaluate_workflow(
        DummyCtx(state),
        "wf-2",
        evaluation=evaluate_payload,
        stream=True,
    )


def test_evaluate_workflow_offline_error() -> None:
    state = make_state()
    state.settings.offline = True
    payload = '{"dataset": {"cases": [{"inputs": {"value": 1}}]}}'

    with pytest.raises(CLIError) as excinfo:
        evaluate_workflow(DummyCtx(state), "wf-1", evaluation=payload)

    assert "Workflow evaluations require network connectivity" in str(excinfo.value)


def test_evaluate_workflow_requires_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    state = make_state()
    payload = '{"dataset": {"cases": [{"inputs": {"value": 1}}]}}'
    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._prepare_streaming_graph",
        lambda *_: None,
    )

    with pytest.raises(CLIError) as excinfo:
        evaluate_workflow(DummyCtx(state), "wf-1", evaluation=payload)

    assert "Evaluation requires streaming mode" in str(excinfo.value)


def test_evaluate_workflow_raises_on_failed_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = make_state()
    payload = '{"dataset": {"cases": [{"inputs": {"value": 1}}]}}'
    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._prepare_streaming_graph",
        lambda *_: ({"nodes": []}, None),
    )

    async def fake_stream(
        state_arg: Any,
        workflow_id: str,
        graph_config: dict[str, Any],
        inputs: Any,
        evaluation: Any,
        *,
        triggered_by: str | None = None,
        runnable_config: Any | None = None,
        stored_runnable_config: Any | None = None,
    ) -> str:
        return "error"

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._stream_workflow_evaluation", fake_stream
    )

    with pytest.raises(CLIError) as excinfo:
        evaluate_workflow(
            DummyCtx(state),
            "wf-1",
            evaluation=payload,
        )

    assert "Workflow evaluation failed" in str(excinfo.value)
