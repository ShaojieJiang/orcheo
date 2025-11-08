"""Workflow show CLI command tests."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from pathlib import Path
import httpx
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def test_workflow_show_uses_cache_when_offline(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {
        "id": "wf-1",
        "name": "Cached",
        "is_public": True,
        "require_login": False,
        "published_at": "2024-01-01T00:00:00Z",
        "publish_token_rotated_at": None,
    }
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
        assert "Share URL: http://api.test/chat/wf-1" in first.stdout

    offline_env = env | {"ORCHEO_PROFILE": "offline"}
    offline_args = ["--offline", "workflow", "show", "wf-1"]
    result = runner.invoke(app, offline_args, env=offline_env)
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout


def test_workflow_show_with_cache_notice(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {
        "id": "wf-1",
        "name": "Cached",
        "is_public": True,
        "require_login": False,
        "published_at": "2024-01-01T00:00:00Z",
        "publish_token_rotated_at": None,
    }
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    runs: list[dict] = []

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
        assert "Status: public" in first.stdout

    # Now test offline with cache showing the notice
    offline_env = env | {"ORCHEO_PROFILE": "offline"}
    result = runner.invoke(
        app, ["--offline", "workflow", "show", "wf-1"], env=offline_env
    )
    assert result.exit_code == 0
    assert "Cached" in result.stdout


def test_workflow_show_no_latest_version(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow show when there's no latest version."""
    workflow = {
        "id": "wf-1",
        "name": "NoVersion",
        "is_public": False,
        "require_login": False,
        "published_at": None,
        "publish_token_rotated_at": None,
    }
    versions: list[dict] = []
    runs: list[dict] = []

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
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0


def test_workflow_show_no_runs(runner: CliRunner, env: dict[str, str]) -> None:
    """Test workflow show when there are no runs."""
    workflow = {
        "id": "wf-1",
        "name": "NoRuns",
        "is_public": True,
        "require_login": True,
        "published_at": "2024-01-01T00:00:00Z",
        "publish_token_rotated_at": "2024-01-02T00:00:00Z",
    }
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    runs: list[dict] = []

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
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0


def test_workflow_show_with_stale_cache_notice(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test workflow show displays stale cache notice."""
    import json

    cache_dir = tmp_path / "stale_wf_cache"
    cache_dir.mkdir(exist_ok=True)

    # Create cache files with 25-hour-old timestamps (older than 24h TTL)
    stale_time = datetime.now(tz=UTC) - timedelta(hours=25)
    workflow = {
        "id": "wf-1",
        "name": "Cached",
        "is_public": True,
        "require_login": False,
        "published_at": "2024-01-01T00:00:00Z",
        "publish_token_rotated_at": None,
    }
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": ["start"], "edges": []}}
    ]
    runs = [{"id": "run-1", "status": "succeeded", "created_at": "2024-01-01"}]

    # Write stale cache files
    for key, data in [
        ("workflow_wf-1", workflow),
        ("workflow_wf-1_versions", versions),
        ("workflow_wf-1_runs", runs),
    ]:
        cache_file = cache_dir / f"{key}.json"
        cache_file.write_text(
            json.dumps({"timestamp": stale_time.isoformat(), "payload": data}),
            encoding="utf-8",
        )

    env_with_cache = env | {"ORCHEO_CACHE_DIR": str(cache_dir)}
    result = runner.invoke(
        app, ["--offline", "workflow", "show", "wf-1"], env=env_with_cache
    )
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
    assert "older than TTL" in result.stdout


def test_workflow_show_with_mermaid_generation(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow show generates mermaid diagram with various edge cases."""
    workflow = {
        "id": "wf-1",
        "name": "Test",
        "is_public": True,
        "require_login": False,
        "published_at": "2024-01-01T00:00:00Z",
        "publish_token_rotated_at": None,
    }
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "nodes": [{"id": "start_node"}, {"id": "end_node"}],
                "edges": [
                    {"from": "START", "to": "start_node"},
                    {"from": "start_node", "to": "end_node"},
                    {"from": "end_node", "to": "END"},
                ],
            },
        }
    ]
    runs: list[dict] = []

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
        result = runner.invoke(app, ["workflow", "show", "wf-1"], env=env)
    assert result.exit_code == 0
    assert "start_node" in result.stdout
    assert "end_node" in result.stdout
