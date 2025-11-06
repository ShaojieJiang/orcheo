"""Workflow download CLI tests for standard formats."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import respx
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def test_workflow_download_json_to_stdout(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download outputs JSON to stdout."""
    workflow = {"id": "wf-1", "name": "Test", "metadata": {"key": "value"}}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [{"id": "a"}], "edges": []},
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],
            env=env,
        )
    assert result.exit_code == 0
    assert '"name": "Test"' in result.stdout
    assert '"metadata"' in result.stdout


def test_workflow_download_json_to_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow download saves JSON to file."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [{"id": "a"}], "edges": []},
        }
    ]
    output_file = tmp_path / "output.json"

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--output", str(output_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "downloaded to" in result.stdout
    assert output_file.exists()
    content = json.loads(output_file.read_text(encoding="utf-8"))
    assert content["name"] == "Test"


def test_workflow_download_python_to_stdout(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download outputs Python code to stdout."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "nodes": [
                    {"name": "node1", "type": "Agent"},
                    {"name": "node2", "type": "Agent"},
                ],
                "edges": [],
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "python"],
            env=env,
        )
    assert result.exit_code == 0
    assert "from orcheo_sdk import Workflow" in result.stdout
    assert "class AgentConfig" in result.stdout
    assert "class AgentNode" in result.stdout


def test_workflow_download_python_to_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow download saves Python code to file."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "nodes": [{"name": "node1", "type": "Code"}],
                "edges": [],
            },
        }
    ]
    output_file = tmp_path / "output.py"

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "download",
                "wf-1",
                "--format",
                "python",
                "-o",
                str(output_file),
            ],
            env=env,
        )
    assert result.exit_code == 0
    assert "downloaded to" in result.stdout
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "from orcheo_sdk import Workflow" in content


def test_workflow_download_no_versions_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download fails when workflow has no versions."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "has no versions" in str(result.exception)


def test_workflow_download_unsupported_format_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download fails with unsupported format."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [], "edges": []},
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "yaml"],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Unsupported format" in str(result.exception)
