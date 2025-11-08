"""Tests for workflow publish-related CLI commands."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import httpx
import respx
from orcheo_sdk.cli.cache import CacheManager
from orcheo_sdk.cli.main import app
from orcheo_sdk.cli.errors import CLIError
from typer.testing import CliRunner


def _read_cache_payload(cache_dir: Path, key: str) -> dict:
    path = cache_dir / f"{key}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["payload"]


def test_workflow_publish_updates_cache_and_outputs_summary(
    runner: CliRunner, env: dict[str, str]
) -> None:
    cache_dir = Path(env["ORCHEO_CACHE_DIR"])
    cache = CacheManager(cache_dir, ttl=timedelta(hours=24))
    cache.store(
        "workflows:archived:False",
        [
            {
                "id": "wf-1",
                "name": "Demo",
                "slug": "demo",
                "is_public": False,
            }
        ],
    )

    response = {
        "workflow": {
            "id": "wf-1",
            "name": "Demo",
            "slug": "demo",
            "is_public": True,
            "require_login": True,
            "published_at": "2024-01-01T00:00:00Z",
            "published_by": "cli",
        },
        "publish_token": "pk-test",
        "message": "Store this publish token securely.",
    }

    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish").mock(
            return_value=httpx.Response(201, json=response)
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "wf-1", "--require-login"],
            env=env,
            input="y\n",
        )

    assert result.exit_code == 0
    assert "Publish details" in result.stdout
    assert "http://api.test/chat/wf-1" in result.stdout
    assert "Publish token" in result.stdout

    workflow_payload = _read_cache_payload(cache_dir, "workflow_wf-1")
    assert workflow_payload["is_public"] is True
    assert workflow_payload["publish_summary"]["require_login"] is True

    list_entry = cache.load("workflows:archived:False")
    assert list_entry is not None
    assert list_entry.payload[0]["is_public"] is True


def test_workflow_publish_handles_missing_workflow(
    runner: CliRunner, env: dict[str, str]
) -> None:
    error_payload = {"detail": {"message": "Workflow not found"}}
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/missing/publish").mock(
            return_value=httpx.Response(404, json=error_payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "missing"],
            env=env,
            input="y\n",
        )

    assert result.exit_code == 1
    assert isinstance(result.exception, CLIError)
    assert "workflow ID" in str(result.exception)


def test_workflow_rotate_token_shows_new_token(
    runner: CliRunner, env: dict[str, str]
) -> None:
    response = {
        "workflow": {
            "id": "wf-1",
            "name": "Demo",
            "slug": "demo",
            "is_public": True,
            "require_login": False,
            "publish_token_rotated_at": "2024-02-02T00:00:00Z",
        },
        "publish_token": "pk-rotated",
        "message": "Rotated",
    }
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish/rotate").mock(
            return_value=httpx.Response(200, json=response)
        )
        result = runner.invoke(
            app,
            ["workflow", "rotate-token", "wf-1"],
            env=env,
            input="y\n",
        )

    assert result.exit_code == 0
    assert "rotated" in result.stdout.lower()
    assert "pk-rotated" in result.stdout


def test_workflow_unpublish_updates_cache(
    runner: CliRunner, env: dict[str, str]
) -> None:
    cache_dir = Path(env["ORCHEO_CACHE_DIR"])
    cache = CacheManager(cache_dir, ttl=timedelta(hours=24))
    cache.store(
        "workflows:archived:False",
        [
            {
                "id": "wf-1",
                "name": "Demo",
                "slug": "demo",
                "is_public": True,
            }
        ],
    )

    response = {
        "id": "wf-1",
        "name": "Demo",
        "slug": "demo",
        "is_public": False,
        "require_login": False,
    }
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish/revoke").mock(
            return_value=httpx.Response(200, json=response)
        )
        result = runner.invoke(
            app,
            ["workflow", "unpublish", "wf-1"],
            env=env,
            input="y\n",
        )

    assert result.exit_code == 0
    assert "no longer public" in result.stdout
    assert "Current publish status" in result.stdout
    assert "private" in result.stdout.lower()

    workflow_payload = _read_cache_payload(cache_dir, "workflow_wf-1")
    assert workflow_payload["is_public"] is False

    list_entry = cache.load("workflows:archived:False")
    assert list_entry is not None
    assert list_entry.payload[0]["is_public"] is False
