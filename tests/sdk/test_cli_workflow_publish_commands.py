from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import httpx
import json
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def _read_cache(cache_dir: Path, key: str) -> dict:
    file_path = cache_dir / f"{key}.json"
    return json.loads(file_path.read_text(encoding="utf-8"))


def test_workflow_publish_success_updates_cache(
    runner: CliRunner, env: dict[str, str]
) -> None:
    cache_dir = Path(env["ORCHEO_CACHE_DIR"])
    # Prime list cache to ensure invalidation occurs
    list_cache = cache_dir / "workflows_archived_False.json"
    list_cache.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "payload": [],
            }
        ),
        encoding="utf-8",
    )

    payload = {
        "workflow": {
            "id": "wf-1",
            "name": "Demo",
            "is_public": True,
            "require_login": False,
            "published_at": "2024-06-01T00:00:00Z",
        },
        "publish_token": "token-123",
        "message": "Store this publish token securely. It will not be shown again.",
    }
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-1/publish").mock(
            return_value=httpx.Response(201, json=payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "wf-1", "--force"],
            env=env,
        )

    assert result.exit_code == 0
    assert "Workflow 'Demo' published successfully." in result.stdout
    assert "Share URL: http://canvas.test/chat/wf-1" in result.stdout
    assert "Publish token: token-123" in result.stdout
    assert "require login" not in result.stdout.lower() or "Require login: no" in result.stdout

    # Cache should contain updated workflow metadata
    workflow_cache = _read_cache(cache_dir, "workflow_wf-1")
    assert workflow_cache["payload"]["is_public"] is True
    assert (cache_dir / "workflows_archived_False.json").exists() is False


def test_workflow_publish_respects_require_login_flag(
    runner: CliRunner, env: dict[str, str]
) -> None:
    payload = {
        "workflow": {
            "id": "wf-2",
            "name": "Secure",
            "is_public": True,
            "require_login": True,
        },
        "publish_token": "tok-secure",
    }
    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://api.test/api/workflows/wf-2/publish").mock(
            return_value=httpx.Response(201, json=payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "wf-2", "--require-login", "--force"],
            env=env,
        )

    assert result.exit_code == 0
    body = json.loads(route.calls[0].request.content.decode())
    assert body["require_login"] is True
    assert "Require login: yes" in result.stdout


def test_workflow_publish_handles_missing_workflow(
    runner: CliRunner, env: dict[str, str]
) -> None:
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/missing/publish").mock(
            return_value=httpx.Response(
                404,
                json={"detail": {"message": "Workflow not found"}},
            )
        )
        result = runner.invoke(
            app,
            ["workflow", "publish", "missing", "--force"],
            env=env,
        )

    assert result.exit_code == 1
    assert "Workflow 'missing' was not found" in str(result.exception)


def test_workflow_publish_requires_network(runner: CliRunner, env: dict[str, str]) -> None:
    result = runner.invoke(
        app,
        ["--offline", "workflow", "publish", "wf-1"],
        env=env,
    )
    assert result.exit_code == 1
    assert "Publishing workflows requires network connectivity" in str(result.exception)


def test_workflow_rotate_token_outputs_new_token(
    runner: CliRunner, env: dict[str, str]
) -> None:
    payload = {
        "workflow": {
            "id": "wf-3",
            "name": "Demo",
            "is_public": True,
        },
        "publish_token": "rotated-token",
    }
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-3/publish/rotate").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(
            app,
            ["workflow", "rotate-token", "wf-3", "--force"],
            env=env,
        )

    assert result.exit_code == 0
    assert "rotated successfully" in result.stdout
    assert "New publish token: rotated-token" in result.stdout


def test_workflow_unpublish_success(runner: CliRunner, env: dict[str, str]) -> None:
    payload = {
        "workflow": {
            "id": "wf-4",
            "name": "Demo",
            "is_public": False,
        }
    }
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/workflows/wf-4/publish/revoke").mock(
            return_value=httpx.Response(200, json=payload["workflow"])
        )
        result = runner.invoke(
            app,
            ["workflow", "unpublish", "wf-4", "--force"],
            env=env,
        )

    assert result.exit_code == 0
    assert "is now private" in result.stdout
