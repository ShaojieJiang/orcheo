"""Tests covering the Orcheo CLI."""

from __future__ import annotations

from pathlib import Path
import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from orcheo_sdk.cli.main import app


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.fixture()
def env(tmp_path: Path) -> dict[str, str]:
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache"
    config_dir.mkdir()
    cache_dir.mkdir()
    return {
        "ORCHEO_API_URL": "http://api.test",
        "ORCHEO_SERVICE_TOKEN": "token",
        "ORCHEO_CONFIG_DIR": str(config_dir),
        "ORCHEO_CACHE_DIR": str(cache_dir),
        "NO_COLOR": "1",
    }


def test_node_list_shows_registered_nodes(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["node", "list"], env=env)
    assert result.exit_code == 0
    assert "WebhookTriggerNode" in result.stdout


def test_workflow_list_renders_table(runner: CliRunner, env: dict[str, str]) -> None:
    payload = [{"id": "wf-1", "name": "Demo", "slug": "demo", "is_archived": False}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list"], env=env)
    assert result.exit_code == 0
    assert "Demo" in result.stdout


def test_workflow_show_uses_cache_when_offline(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Cached"}
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    runs = [{"id": "run-1", "status": "succeeded", "created_at": "2024-01-01"}]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        first = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
        assert first.exit_code == 0

    offline_env = env | {"ORCHEO_PROFILE": "offline"}
    offline_args = ["--offline", "workflow", "show", "wf-1"]
    result = runner.invoke(app, offline_args, env=offline_env)
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout


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


def test_credential_create_and_delete(runner: CliRunner, env: dict[str, str]) -> None:
    created = {"id": "cred-1", "name": "Canvas", "provider": "api"}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/credentials").mock(
            return_value=httpx.Response(201, json=created)
        )
        router.delete("http://api.test/api/credentials/cred-1").mock(
            return_value=httpx.Response(204)
        )
        create_result = runner.invoke(
            app,
            [
                "credential",
                "create",
                "Canvas",
                "--provider",
                "api",
                "--secret",
                "secret",
            ],
            env=env,
        )
        assert create_result.exit_code == 0

        delete_result = runner.invoke(
            app,
            [
                "credential",
                "delete",
                "cred-1",
                "--force",
            ],
            env=env,
        )
    assert delete_result.exit_code == 0


def test_credential_reference_outputs_snippet(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["credential", "reference", "Canvas"], env=env)
    assert result.exit_code == 0
    assert "[[Canvas]]" in result.stdout


def test_code_scaffold_uses_cache_offline(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Cached"}
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        first = runner.invoke(app, ["code", "scaffold", "wf-1"], env=env)
        assert first.exit_code == 0

    offline_env = env | {"ORCHEO_PROFILE": "offline"}
    result = runner.invoke(
        app, ["--offline", "code", "scaffold", "wf-1"], env=offline_env
    )
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
    assert "HttpWorkflowExecutor" in result.stdout
