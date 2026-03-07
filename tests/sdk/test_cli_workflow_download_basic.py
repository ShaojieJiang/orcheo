"""Workflow download CLI tests for Python-only export behavior."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


SCRIPT_V1 = "from langgraph.graph import StateGraph\n"
SCRIPT_V2 = "from langgraph.graph import StateGraph\n# v2\n"


def _version(version: int, source: str) -> dict[str, object]:
    return {
        "id": f"ver-{version}",
        "version": version,
        "graph": {
            "format": "langgraph-script",
            "source": source,
            "entrypoint": None,
            "summary": {"nodes": [], "edges": []},
        },
    }


def test_workflow_download_defaults_to_python_stdout(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [_version(1, SCRIPT_V1)]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["workflow", "download", "wf-1"], env=env)
    assert result.exit_code == 0
    assert SCRIPT_V1 in result.stdout


def test_workflow_download_specific_version(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Test"}
    version_two = _version(2, SCRIPT_V2)

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions/2").mock(
            return_value=httpx.Response(200, json=version_two)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--version", "2"],
            env=env,
        )
    assert result.exit_code == 0
    assert SCRIPT_V2 in result.stdout


def test_workflow_download_to_file_machine_mode(
    runner: CliRunner, machine_env: dict[str, str], tmp_path: Path
) -> None:
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [_version(1, SCRIPT_V1)]
    output_file = tmp_path / "workflow.py"

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
            env=machine_env,
        )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert output_file.read_text(encoding="utf-8") == SCRIPT_V1


def test_workflow_download_rejects_non_python_format(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [_version(1, SCRIPT_V1)]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "json"],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Unsupported format" in str(result.exception)


def test_workflow_download_no_versions_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Test"}

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=[])
        )
        result = runner.invoke(app, ["workflow", "download", "wf-1"], env=env)
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "has no versions" in str(result.exception)
