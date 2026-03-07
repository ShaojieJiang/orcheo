"""Workflow upload tests for removed JSON upload support."""

from __future__ import annotations
import json
from pathlib import Path
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


def test_workflow_upload_json_file_is_rejected(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """JSON workflow uploads should fail with guidance."""
    json_file = tmp_path / "workflow.json"
    json_file.write_text(
        json.dumps({"name": "TestWorkflow", "graph": {"nodes": [], "edges": []}}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["workflow", "upload", str(json_file)], env=env)
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Only .py files are supported" in str(result.exception)


def test_workflow_upload_json_file_with_config_is_rejected(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """JSON upload rejection still applies when config flags are provided."""
    json_file = tmp_path / "workflow.json"
    json_file.write_text(
        json.dumps({"name": "TestWorkflow", "graph": {"nodes": [], "edges": []}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "workflow",
            "upload",
            str(json_file),
            "--config",
            '{"tags": ["alpha"], "max_concurrency": 3}',
        ],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Only .py files are supported" in str(result.exception)
