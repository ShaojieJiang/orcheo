"""Workflow download CLI tests for standard formats."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


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


def test_workflow_download_machine_mode_no_output_path(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """Machine mode download without --output prints raw JSON payload."""
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
            env=machine_env,
        )
    assert result.exit_code == 0
    assert '"content"' in result.stdout


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


def test_workflow_download_specific_version(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download with --version option fetches specific version."""
    workflow = {"id": "wf-1", "name": "Test"}
    version_2 = {
        "id": "ver-2",
        "version": 2,
        "graph": {"nodes": [{"id": "node_v2"}], "edges": []},
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions/2").mock(
            return_value=httpx.Response(200, json=version_2)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--version", "2"],
            env=env,
        )
    assert result.exit_code == 0
    assert "node_v2" in result.stdout


def test_workflow_download_specific_version_short_option(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download with -v short option."""
    workflow = {"id": "wf-1", "name": "Test"}
    version_1 = {
        "id": "ver-1",
        "version": 1,
        "graph": {"nodes": [{"id": "node_v1"}], "edges": []},
    }

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions/1").mock(
            return_value=httpx.Response(200, json=version_1)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "-v", "1"],
            env=env,
        )
    assert result.exit_code == 0
    assert "node_v1" in result.stdout


def test_workflow_download_specific_version_to_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow download with --version saves specific version to file."""
    workflow = {"id": "wf-1", "name": "TestV3"}
    version_3 = {
        "id": "ver-3",
        "version": 3,
        "graph": {"nodes": [{"id": "node_v3"}], "edges": []},
    }
    output_file = tmp_path / "output.json"

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions/3").mock(
            return_value=httpx.Response(200, json=version_3)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--version", "3", "-o", str(output_file)],
            env=env,
        )
    assert result.exit_code == 0
    assert "downloaded to" in result.stdout
    assert output_file.exists()
    content = json.loads(output_file.read_text(encoding="utf-8"))
    assert content["name"] == "TestV3"
