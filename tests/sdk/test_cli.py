"""Tests for the Orcheo CLI entry point."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from orcheo_sdk.cli import app as cli_app
from orcheo_sdk.cli.runtime import CacheEntry
from orcheo_sdk.cli.services import (
    CredentialRecord,
    NodeRecord,
    WorkflowDetail,
    WorkflowRunInfo,
    WorkflowVersionInfo,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORCHEO_CACHE_DIR", str(tmp_path / "cache"))


def _fresh_entry(data: object | None = None) -> CacheEntry:
    return CacheEntry(data=data, cached_at=datetime.now(tz=UTC))


def test_node_list_uses_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    record = NodeRecord(
        name="Agent",
        description="Execute AI agents",
        category="ai",
        tags=("ai", "llm"),
    )

    monkeypatch.setattr(
        "orcheo_sdk.cli.commands.nodes.fetch_node_catalog",
        lambda runtime: ([record], True, _fresh_entry([record.to_dict()])),
    )

    result = runner.invoke(cli_app, ["--offline", "node", "list"])
    assert result.exit_code == 0
    assert "Agent" in result.stdout
    assert "ai" in result.stdout


def test_workflow_show_renders_mermaid(monkeypatch: pytest.MonkeyPatch) -> None:
    detail = WorkflowDetail(
        id="wf-1",
        name="Test Workflow",
        slug="test-workflow",
        tags=("demo",),
        is_archived=False,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
        description="Demo",
    )
    version = WorkflowVersionInfo(
        id="ver-1",
        version=1,
        created_at=datetime.now(tz=UTC),
        notes=None,
        graph={
            "nodes": [
                {"name": "start", "type": "Trigger"},
                {"name": "end", "type": "Action"},
            ],
            "edges": [("start", "end")],
            "conditional_edges": [],
        },
    )

    monkeypatch.setattr(
        "orcheo_sdk.cli.commands.workflows.fetch_workflow_detail",
        lambda runtime, workflow_id: (detail, [version], _fresh_entry()),
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.commands.workflows.fetch_workflow_runs",
        lambda runtime, workflow_id: [
            WorkflowRunInfo(
                id="run-1",
                status="succeeded",
                triggered_by="tester",
                created_at=datetime.now(tz=UTC),
                started_at=datetime.now(tz=UTC),
                completed_at=datetime.now(tz=UTC),
            )
        ],
    )

    result = runner.invoke(cli_app, ["--offline", "workflow", "show", "wf-1"])
    assert result.exit_code == 0
    assert "Workflow: Test Workflow" in result.stdout
    assert "Mermaid diagram" in result.stdout
    assert "run-1" in result.stdout


def test_workflow_run_triggers_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    detail = WorkflowDetail(
        id="wf-2",
        name="Another Workflow",
        slug="another",
        tags=(),
        is_archived=False,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
        description=None,
    )
    version = WorkflowVersionInfo(
        id="ver-2",
        version=2,
        created_at=datetime.now(tz=UTC),
        notes=None,
        graph={"nodes": [], "edges": [], "conditional_edges": []},
    )

    monkeypatch.setattr(
        "orcheo_sdk.cli.commands.workflows.fetch_workflow_detail",
        lambda runtime, workflow_id: (detail, [version], None),
    )

    captured: dict[str, object] = {}

    def _trigger(runtime, *, workflow_id, workflow_version_id, actor, inputs):
        captured.update(
            {
                "workflow_id": workflow_id,
                "workflow_version_id": workflow_version_id,
                "actor": actor,
                "inputs": inputs,
            }
        )
        return WorkflowRunInfo(
            id="run-42",
            status="pending",
            triggered_by=actor,
            created_at=datetime.now(tz=UTC),
            started_at=None,
            completed_at=None,
        )

    monkeypatch.setattr(
        "orcheo_sdk.cli.commands.workflows.trigger_workflow_run",
        _trigger,
    )

    result = runner.invoke(
        cli_app,
        ["workflow", "run", "wf-2", "--version", "2", "--inputs", '{"key": "value"}'],
    )
    assert result.exit_code == 0
    assert captured["workflow_id"] == "wf-2"
    assert captured["workflow_version_id"] == "ver-2"
    assert captured["inputs"] == {"key": "value"}
    assert "run-42" in result.stdout


def test_credential_reference_outputs_snippet(monkeypatch: pytest.MonkeyPatch) -> None:
    credential = CredentialRecord(
        id="cred-1",
        name="Prod API",
        provider="example",
        access="private",
        status="healthy",
        kind="secret",
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.commands.credentials.fetch_credentials",
        lambda runtime, workflow_id=None: [credential],
    )

    result = runner.invoke(cli_app, ["credential", "reference", "Prod API"])
    assert result.exit_code == 0
    assert "[[Prod API]]" in result.stdout


def test_code_scaffold_uses_cached_version(monkeypatch: pytest.MonkeyPatch) -> None:
    detail = WorkflowDetail(
        id="wf-3",
        name="Scaffold Workflow",
        slug="scaffold",
        tags=(),
        is_archived=False,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
        description=None,
    )
    version = WorkflowVersionInfo(
        id="ver-3",
        version=3,
        created_at=datetime.now(tz=UTC),
        notes=None,
        graph={"nodes": [], "edges": [], "conditional_edges": []},
    )

    monkeypatch.setattr(
        "orcheo_sdk.cli.commands.code.fetch_workflow_detail",
        lambda runtime, workflow_id: (detail, [version], _fresh_entry()),
    )

    result = runner.invoke(
        cli_app, ["--offline", "code", "scaffold", "wf-3", "--version", "3"]
    )
    assert result.exit_code == 0
    assert 'workflow_version_id="ver-3"' in result.stdout
    assert "ORCHEO_SERVICE_TOKEN" in result.stdout
