"""Workflow upload tests for Python sources."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import pytest
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


def test_workflow_upload_python_file_create_new(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload creates new workflow from Python file."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from orcheo_sdk import Workflow

workflow = Workflow(name="TestWorkflow")
""",
        encoding="utf-8",
    )

    created = {"id": "wf-new", "name": "TestWorkflow"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "uploaded successfully" in result.stdout


def test_workflow_upload_python_file_update_existing(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload updates existing workflow from Python file."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from orcheo_sdk import Workflow

workflow = Workflow(name="TestWorkflow")
""",
        encoding="utf-8",
    )

    updated = {"id": "wf-1", "name": "TestWorkflow"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--id", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert "updated successfully" in result.stdout


def test_workflow_upload_python_file_create_new_with_name_override(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload allows renaming when creating from Python file."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from orcheo_sdk import Workflow

workflow = Workflow(name="TestWorkflow")
""",
        encoding="utf-8",
    )

    created = {"id": "wf-new", "name": "Renamed Workflow"}
    with respx.mock(assert_all_called=True) as router:
        create_route = router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=created)
        )
        result = runner.invoke(
            app,
            ["workflow", "upload", str(py_file), "--name", "Renamed Workflow"],
            env=env,
        )
    assert result.exit_code == 0
    body = json.loads(create_route.calls[0].request.content)
    assert body["name"] == "Renamed Workflow"


def test_workflow_upload_python_file_update_existing_with_name_override(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow upload allows renaming when updating from Python file."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from orcheo_sdk import Workflow

workflow = Workflow(name="OldName")
""",
        encoding="utf-8",
    )

    updated = {"id": "wf-1", "name": "Renamed Workflow"}
    with respx.mock(assert_all_called=True) as router:
        update_route = router.post("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "upload",
                str(py_file),
                "--id",
                "wf-1",
                "--name",
                "Renamed Workflow",
            ],
            env=env,
        )
    assert result.exit_code == 0
    body = json.loads(update_route.calls[0].request.content)
    assert body["name"] == "Renamed Workflow"


def test_workflow_upload_python_spec_loading_failure(
    runner: CliRunner,
    env: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test workflow upload handles spec_from_file_location failure."""
    import importlib.util

    py_file = tmp_path / "workflow.py"
    py_file.write_text("workflow = None", encoding="utf-8")

    # Mock spec_from_file_location to return None
    def mock_spec_from_file_location(name: str, location: object) -> None:
        return None

    monkeypatch.setattr(
        importlib.util, "spec_from_file_location", mock_spec_from_file_location
    )

    result = runner.invoke(
        app,
        ["workflow", "upload", str(py_file)],
        env=env,
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Failed to load Python module" in str(result.exception)
