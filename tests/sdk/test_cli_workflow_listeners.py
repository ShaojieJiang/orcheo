"""Workflow listener CLI command tests."""

from __future__ import annotations
import json
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


def test_workflow_listener_pause_human_mode(
    runner: CliRunner, env: dict[str, str]
) -> None:
    payload = {
        "subscription_id": "sub-1",
        "status": "paused",
        "runtime_status": "stopped",
    }

    with respx.mock(assert_all_called=True) as router:
        route = router.post(
            "http://api.test/api/workflows/wf-1/listeners/sub-1/pause"
        ).mock(return_value=httpx.Response(200, json=payload))
        result = runner.invoke(
            app,
            ["workflow", "listeners", "pause", "wf-1", "sub-1", "--actor", "tester"],
            env=env,
        )

    assert result.exit_code == 0
    assert "pause" in result.stdout.lower()
    assert "sub-1" in result.stdout
    assert json.loads(route.calls[0].request.content) == {"actor": "tester"}


def test_workflow_listener_resume_machine_mode(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    payload = {
        "subscription_id": "sub-1",
        "status": "active",
        "runtime_status": "starting",
    }

    with respx.mock(assert_all_called=True) as router:
        route = router.post(
            "http://api.test/api/workflows/wf-1/listeners/sub-1/resume"
        ).mock(return_value=httpx.Response(200, json=payload))
        result = runner.invoke(
            app,
            ["workflow", "listeners", "resume", "wf-1", "sub-1"],
            env=machine_env,
        )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == payload
    assert json.loads(route.calls[0].request.content) == {"actor": "cli"}


def test_workflow_listener_control_requires_connectivity(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        ["--offline", "workflow", "listeners", "pause", "wf-1", "sub-1"],
        env=env,
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "network connectivity" in str(result.exception)


def test_workflow_listener_pause_non_mapping_response_returns_empty_dict(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """Covers line 57 of services/workflows/listeners.py: non-Mapping payload → {}."""
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/listeners/sub-1/pause").mock(
            return_value=httpx.Response(200, json=["unexpected", "list"])
        )
        result = runner.invoke(
            app,
            ["workflow", "listeners", "pause", "wf-1", "sub-1", "--actor", "tester"],
            env=machine_env,
        )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {}
