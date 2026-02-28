"""Workflow update CLI command tests."""

from __future__ import annotations
import json
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


def test_workflow_update_accepts_handle_and_updates_name_and_handle(
    runner: CliRunner, env: dict[str, str]
) -> None:
    updated = {
        "id": "wf-1",
        "handle": "renamed-workflow",
        "name": "Renamed Workflow",
        "description": "Updated from CLI",
    }

    with respx.mock(assert_all_called=True) as router:
        update_route = router.put(
            "http://api.test/api/workflows/original-workflow"
        ).mock(return_value=httpx.Response(200, json=updated))
        result = runner.invoke(
            app,
            [
                "workflow",
                "update",
                "original-workflow",
                "--name",
                "Renamed Workflow",
                "--handle",
                "renamed-workflow",
                "--description",
                "Updated from CLI",
            ],
            env=env,
        )

    assert result.exit_code == 0
    assert "updated successfully" in result.stdout
    request_body = json.loads(update_route.calls[0].request.content)
    assert request_body["name"] == "Renamed Workflow"
    assert request_body["handle"] == "renamed-workflow"
    assert request_body["description"] == "Updated from CLI"


def test_workflow_update_requires_connectivity(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        ["--offline", "workflow", "update", "wf-1", "--name", "Renamed Workflow"],
        env=env,
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "network connectivity" in str(result.exception)


def test_workflow_update_requires_at_least_one_field(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        ["workflow", "update", "wf-1"],
        env=env,
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Provide at least one field to update." in str(result.exception)


def test_workflow_update_machine_mode_prints_json(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    updated = {
        "id": "wf-1",
        "handle": "renamed-workflow",
        "name": "Renamed Workflow",
    }

    with respx.mock(assert_all_called=True) as router:
        router.put("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        result = runner.invoke(
            app,
            ["workflow", "update", "wf-1", "--name", "Renamed Workflow"],
            env=machine_env,
        )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == updated
