from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from orcheo_sdk.cli.cache import CacheManager
from orcheo_sdk.cli.errors import APICallError
from orcheo_sdk.cli.main import app
from orcheo_sdk.cli.workflow.commands.publishing import _update_workflow_cache


def _publish_response(require_login: bool = False) -> dict[str, object]:
    return {
        "workflow": {
            "id": "wf-1",
            "name": "Demo",
            "is_public": True,
            "require_login": require_login,
            "published_at": "2024-01-01T00:00:00Z",
        },
        "publish_token": "token-secret",
        "message": "Store token",
    }


def test_publish_workflow_success(runner: CliRunner, env: dict[str, str]) -> None:
    payload = _publish_response(require_login=True)
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish").mock(
            return_value=httpx.Response(201, json=payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "wf-1", "--require-login", "--force"],
            env=env,
        )

    assert result.exit_code == 0
    assert "Workflow visibility updated successfully" in result.stdout
    assert "Require login: Yes" in result.stdout
    assert "http://api.test/chat/wf-1" in result.stdout
    assert result.stdout.count("token-secret") == 1


def test_publish_workflow_not_found(runner: CliRunner, env: dict[str, str]) -> None:
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/missing/publish").mock(
            return_value=httpx.Response(
                404, json={"detail": {"message": "Workflow not found"}}
            )
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "missing", "--force"],
            env=env,
        )

    assert result.exit_code == 1
    assert isinstance(result.exception, APICallError)
    assert "Workflow 'missing' was not found" in str(result.exception)


def test_publish_workflow_forbidden(runner: CliRunner, env: dict[str, str]) -> None:
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish").mock(
            return_value=httpx.Response(
                403, json={"detail": {"message": "Forbidden"}}
            )
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "wf-1", "--force"],
            env=env,
        )

    assert result.exit_code == 1
    assert isinstance(result.exception, APICallError)
    assert "Permission denied when modifying workflow 'wf-1'" in str(result.exception)


def test_rotate_publish_token_success(runner: CliRunner, env: dict[str, str]) -> None:
    payload = _publish_response()
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish/rotate").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "rotate-token", "wf-1", "--force"],
            env=env,
        )

    assert result.exit_code == 0
    assert "Previous tokens can no longer start new chat sessions" in result.stdout


def test_unpublish_workflow_success(runner: CliRunner, env: dict[str, str]) -> None:
    workflow = {
        "id": "wf-1",
        "name": "Demo",
        "is_public": False,
        "require_login": False,
    }
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish/revoke").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        result = runner.invoke(
            app,
            ["workflow", "unpublish", "wf-1", "--force"],
            env=env,
        )

    assert result.exit_code == 0
    assert "Workflow is now private" in result.stdout
    assert "Share URL: -" in result.stdout


def test_update_workflow_cache_updates_entries(tmp_path: Path) -> None:
    cache = CacheManager(directory=tmp_path / "cache", ttl=timedelta(hours=1))
    workflow = {
        "id": "wf-1",
        "is_public": True,
        "share_url": "http://api.test/chat/wf-1",
        "is_archived": False,
    }
    cache.store(
        "workflows:archived:False",
        [{"id": "wf-1", "is_public": False, "share_url": None, "is_archived": False}],
    )

    _update_workflow_cache(cache, workflow)

    entry = cache.load("workflow:wf-1")
    assert entry is not None
    assert entry.payload["share_url"] == "http://api.test/chat/wf-1"

    list_entry = cache.load("workflows:archived:False")
    assert list_entry is not None
    payload = list_entry.payload
    assert isinstance(payload, list)
    assert payload[0]["share_url"] == "http://api.test/chat/wf-1"


def test_update_workflow_cache_removes_from_archived(tmp_path: Path) -> None:
    cache = CacheManager(directory=tmp_path / "cache2", ttl=timedelta(hours=1))
    workflow = {
        "id": "wf-archived",
        "is_public": True,
        "share_url": "http://api.test/chat/wf-archived",
        "is_archived": False,
    }
    cache.store(
        "workflows:archived:True",
        [{"id": "wf-archived", "is_public": True, "is_archived": True}],
    )

    _update_workflow_cache(cache, workflow)

    archived_entry = cache.load("workflows:archived:True")
    assert archived_entry is not None
    assert archived_entry.payload == []
