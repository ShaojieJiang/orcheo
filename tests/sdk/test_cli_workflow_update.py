"""Workflow update CLI command tests."""

from __future__ import annotations
import json
import httpx
import respx
from typer.testing import CliRunner
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
