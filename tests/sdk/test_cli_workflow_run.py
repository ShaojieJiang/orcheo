"""Workflow run CLI command tests."""

from __future__ import annotations
import json
from pathlib import Path
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


def test_workflow_run_triggers_execution(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    run_response = {"id": "run-1", "status": "pending"}

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        recorded = router.post("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(201, json=run_response)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--actor", "cli"],
            env=env,
        )
    assert result.exit_code == 0
    assert recorded.called
    request = recorded.calls[0].request
    assert request.headers["Authorization"] == "Bearer token"
    assert json.loads(request.content)["triggered_by"] == "cli"


def test_workflow_run_offline_error(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(
        app,
        ["--offline", "workflow", "run", "wf-1"],
        env=env,
    )
    assert result.exit_code != 0


def test_workflow_run_no_versions_error(runner: CliRunner, env: dict[str, str]) -> None:
    versions: list[dict] = []
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["workflow", "run", "wf-1"], env=env)
    assert result.exit_code != 0


def test_workflow_run_no_version_id_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"version": 1}]  # Missing id field
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["workflow", "run", "wf-1"], env=env)
    assert result.exit_code != 0


def test_workflow_run_with_inputs_string(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    run_response = {"id": "run-1", "status": "pending"}

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        recorded = router.post("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(201, json=run_response)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs", '{"key": "value"}'],
            env=env,
        )
    assert result.exit_code == 0
    request_body = json.loads(recorded.calls[0].request.content)
    # The SDK uses input_payload, not inputs
    assert "input_payload" in request_body
    assert request_body["input_payload"]["key"] == "value"


def test_workflow_run_with_inputs_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    run_response = {"id": "run-1", "status": "pending"}
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('{"key": "value"}', encoding="utf-8")

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        recorded = router.post("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(201, json=run_response)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs-file", str(inputs_file)],
            env=env,
        )
    assert result.exit_code == 0
    request_body = json.loads(recorded.calls[0].request.content)
    # The SDK uses input_payload, not inputs
    assert "input_payload" in request_body
    assert request_body["input_payload"]["key"] == "value"


def test_workflow_run_both_inputs_error(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('{"key": "value"}', encoding="utf-8")
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "run",
                "wf-1",
                "--inputs",
                "{}",
                "--inputs-file",
                str(inputs_file),
            ],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "either --inputs or --inputs-file" in str(result.exception).lower()


def test_workflow_run_inputs_file_not_exists(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs-file", "/nonexistent/file.json"],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "does not exist" in str(result.exception)


def test_workflow_run_inputs_file_not_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs-file", str(tmp_path)],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "is not a file" in str(result.exception)


def test_workflow_run_inputs_file_not_json_object(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('["array"]', encoding="utf-8")
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs-file", str(inputs_file)],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must be a JSON object" in str(result.exception)


def test_workflow_run_inputs_string_not_json_object(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [{"id": "ver-1", "version": 1}]
    with respx.mock(assert_all_called=False) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--inputs", '["array"]'],
            env=env,
        )
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "must be a JSON object" in str(result.exception)


def test_workflow_run_inputs_invalid_json(
    runner: CliRunner, env: dict[str, str]
) -> None:
    # This test might not trigger the error because typer might fail earlier
    # but we still test the path
    result = runner.invoke(
        app,
        ["workflow", "run", "wf-1", "--inputs", "{invalid json}"],
        env=env,
    )
    # Should fail due to invalid JSON
    assert result.exit_code != 0


def test_workflow_run_machine_mode_no_stream(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """Machine mode run with --no-stream prints raw JSON result."""
    versions = [{"id": "ver-1", "version": 1}]
    run_response = {"id": "run-1", "status": "pending"}

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.post("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(201, json=run_response)
        )
        result = runner.invoke(
            app,
            ["workflow", "run", "wf-1", "--no-stream"],
            env=machine_env,
        )
    assert result.exit_code == 0
    assert '"run-1"' in result.stdout
