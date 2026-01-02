"""Workflow show CLI command tests."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from pathlib import Path
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.main import app


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


def test_workflow_show_with_cache_notice(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Cached"}
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
    workflow = {"id": "wf-1", "name": "NoVersion"}
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
    workflow = {"id": "wf-1", "name": "NoRuns"}
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
    workflow = {"id": "wf-1", "name": "Cached"}
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
    workflow = {"id": "wf-1", "name": "Test"}
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


def test_workflow_show_with_specific_version(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow show with --version option fetches specific version."""
    workflow = {"id": "wf-1", "name": "Test"}
    version_2 = {
        "id": "ver-2",
        "version": 2,
        "graph": {
            "nodes": [{"id": "node_v2"}],
            "edges": [],
        },
    }
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions/2").mock(
            return_value=httpx.Response(200, json=version_2)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        result = runner.invoke(
            app, ["workflow", "show", "wf-1", "--version", "2"], env=env
        )
    assert result.exit_code == 0
    assert "Version 2" in result.stdout
    assert "node_v2" in result.stdout


def test_workflow_show_with_version_short_option(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow show with -v short option."""
    workflow = {"id": "wf-1", "name": "Test"}
    version_1 = {
        "id": "ver-1",
        "version": 1,
        "graph": {
            "nodes": [{"id": "node_v1"}],
            "edges": [],
        },
    }
    runs: list[dict] = []

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions/1").mock(
            return_value=httpx.Response(200, json=version_1)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        result = runner.invoke(app, ["workflow", "show", "wf-1", "-v", "1"], env=env)
    assert result.exit_code == 0
    assert "Version 1" in result.stdout
    assert "node_v1" in result.stdout


def test_workflow_show_without_version_shows_latest(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow show without --version shows latest version."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {"id": "ver-1", "version": 1, "graph": {"nodes": [], "edges": []}},
        {
            "id": "ver-2",
            "version": 2,
            "graph": {"nodes": [{"id": "latest"}], "edges": []},
        },
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
    assert "Latest version" in result.stdout
    assert "latest" in result.stdout
