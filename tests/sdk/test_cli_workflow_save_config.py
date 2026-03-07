"""CLI tests for config-only workflow version updates."""

from __future__ import annotations
import json
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


def test_workflow_save_config_updates_latest_version(
    runner: CliRunner, env: dict[str, str]
) -> None:
    versions = [
        {"id": "ver-1", "version": 1},
        {"id": "ver-2", "version": 2},
    ]

    with respx.mock(assert_all_called=True) as router:
        list_route = router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        put_route = router.put(
            "http://api.test/api/workflows/wf-1/versions/2/runnable-config"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"id": "ver-2", "version": 2, "runnable_config": {"tags": ["x"]}},
            )
        )
        result = runner.invoke(
            app,
            [
                "workflow",
                "save-config",
                "wf-1",
                "--config",
                '{"tags": ["x"]}',
            ],
            env=env,
        )

    assert result.exit_code == 0
    request_payload = json.loads(put_route.calls[0].request.content)
    assert request_payload["runnable_config"] == {"tags": ["x"]}
    assert request_payload["actor"] == "cli"
    assert list_route.calls


def test_workflow_save_config_clear(runner: CliRunner, env: dict[str, str]) -> None:
    with respx.mock(assert_all_called=True) as router:
        router.put(
            "http://api.test/api/workflows/wf-1/versions/3/runnable-config"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"id": "ver-3", "version": 3, "runnable_config": None},
            )
        )
        result = runner.invoke(
            app,
            ["workflow", "save-config", "wf-1", "--version", "3", "--clear"],
            env=env,
        )
    assert result.exit_code == 0


def test_workflow_save_config_requires_payload_or_clear(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["workflow", "save-config", "wf-1"], env=env)
    assert result.exit_code != 0
    assert isinstance(result.exception, CLIError)
    assert "Provide --config, --config-file, or --clear" in str(result.exception)
