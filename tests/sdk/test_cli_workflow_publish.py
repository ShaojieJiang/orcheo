"""Tests for workflow publish CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def _cache_file(cache_dir: Path, key: str) -> Path:
    safe = key.replace(":", "_")
    return cache_dir / f"{safe}.json"


def test_publish_workflow_success(runner: CliRunner, env: dict[str, str]) -> None:
    workflow = {
        "id": "wf-1",
        "name": "Demo",
        "is_public": True,
        "require_login": False,
        "published_at": "2024-01-01T00:00:00Z",
        "publish_token_rotated_at": None,
        "share_url": "http://api.test/chat/wf-1",
    }
    payload = {
        "workflow": workflow,
        "publish_token": "publish-token-value",
        "message": "Store this publish token securely.",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish").mock(
            return_value=httpx.Response(201, json=payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "wf-1"],
            env=env,
            input="y\n",
        )

    assert result.exit_code == 0
    assert "Share URL: http://api.test/chat/wf-1" in result.stdout
    assert "Publish token:" in result.stdout

    cache_dir = Path(env["ORCHEO_CACHE_DIR"])
    workflow_cache = json.loads(
        _cache_file(cache_dir, "workflow:wf-1").read_text(encoding="utf-8")
    )
    assert workflow_cache["payload"]["share_url"] == "http://api.test/chat/wf-1"


def test_publish_workflow_require_login_flag(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {
        "id": "wf-2",
        "name": "Secure",
        "is_public": True,
        "require_login": True,
        "published_at": "2024-01-01T00:00:00Z",
        "publish_token_rotated_at": None,
        "share_url": "http://api.test/chat/wf-2",
    }
    payload = {
        "workflow": workflow,
        "publish_token": "secure-token",
        "message": None,
    }

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://api.test/api/workflows/wf-2/publish").mock(
            return_value=httpx.Response(201, json=payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "wf-2", "--require-login", "--yes"],
            env=env,
        )

    assert result.exit_code == 0
    sent_payload = json.loads(route.calls[0].request.content)
    assert sent_payload["require_login"] is True
    assert "OAuth login required: yes" in result.stdout


def test_publish_workflow_missing_workflow(
    runner: CliRunner, env: dict[str, str]
) -> None:
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/missing/publish").mock(
            return_value=httpx.Response(404, json={"detail": {"message": "not found"}})
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "missing", "--yes"],
            env=env,
        )

    assert result.exit_code != 0
    assert "Workflow 'missing' was not found" in str(result.exception)


def test_rotate_publish_token_success(runner: CliRunner, env: dict[str, str]) -> None:
    workflow = {
        "id": "wf-3",
        "name": "Rotate",
        "is_public": True,
        "require_login": False,
        "published_at": "2024-01-01T00:00:00Z",
        "publish_token_rotated_at": "2024-01-02T00:00:00Z",
        "share_url": "http://api.test/chat/wf-3",
    }
    payload = {
        "workflow": workflow,
        "publish_token": "rotated-token",
        "message": "Store this publish token securely.",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-3/publish/rotate").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "rotate-token", "wf-3", "--yes"],
            env=env,
        )

    assert result.exit_code == 0
    assert "New publish token:" in result.stdout
    assert "Share URL: http://api.test/chat/wf-3" in result.stdout


def test_unpublish_workflow_success(runner: CliRunner, env: dict[str, str]) -> None:
    workflow = {
        "id": "wf-4",
        "name": "Unpublish",
        "is_public": False,
        "require_login": False,
        "published_at": None,
        "publish_token_rotated_at": None,
        "share_url": None,
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-4/publish/revoke").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        result = runner.invoke(
            app,
            ["workflow", "unpublish", "wf-4", "--yes"],
            env=env,
        )

    assert result.exit_code == 0
    assert "Workflow 'wf-4' is no longer public." in result.stdout


def test_publish_commands_fail_offline(runner: CliRunner, env: dict[str, str]) -> None:
    offline_env = env | {"ORCHEO_PROFILE": "offline"}
    result = runner.invoke(
        app,
        ["--offline", "workflow", "publish", "wf-1", "--yes"],
        env=offline_env,
    )
    assert result.exit_code != 0
    assert "requires network connectivity" in str(result.exception)
