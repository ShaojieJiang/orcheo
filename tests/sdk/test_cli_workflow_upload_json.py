"""Workflow upload tests for JSON sources."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.main import app


def test_workflow_upload_json_file_create_new(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload creates new workflow from JSON file."""
    json_file = tmp_path / "workflow.json"
    json_file.write_text(
        json.dumps({"name": "TestWorkflow", "graph": {"nodes": [], "edges": []}}),
        encoding="utf-8",
    )

    created = {"id": "wf-new", "name": "TestWorkflow"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(json_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "uploaded successfully" in result.stdout


def test_workflow_upload_json_file_update_existing(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload updates existing workflow from JSON file."""
    json_file = tmp_path / "workflow.json"
    json_file.write_text(
        json.dumps({"name": "TestWorkflow", "graph": {"nodes": [], "edges": []}}),
        encoding="utf-8",
    )

    updated = {"id": "wf-1", "name": "TestWorkflow"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(json_file), "--id", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert "updated successfully" in result.stdout
