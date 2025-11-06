"""Code scaffold CLI command tests."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from pathlib import Path
import httpx
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


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


def test_code_scaffold_no_versions_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Empty"}
    versions: list[dict] = []
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["code", "scaffold", "wf-1"], env=env)
    assert result.exit_code != 0


def test_code_scaffold_no_version_id_error(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "NoID"}
    versions = [{"version": 1}]  # Missing id field
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(app, ["code", "scaffold", "wf-1"], env=env)
    assert result.exit_code != 0


def test_code_scaffold_with_custom_actor(
    runner: CliRunner, env: dict[str, str]
) -> None:
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [{"id": "ver-1", "version": 1}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app, ["code", "scaffold", "wf-1", "--actor", "custom"], env=env
        )
    assert result.exit_code == 0
    assert "custom" in result.stdout


def test_code_scaffold_with_both_stale_caches(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test scaffold shows stale notice when both workflow and versions are stale."""
    import json

    cache_dir = tmp_path / "stale_cache"
    cache_dir.mkdir(exist_ok=True)

    # Create cache files with timestamps from 25 hours ago (older than default 24h TTL)
    stale_time = datetime.now(tz=UTC) - timedelta(hours=25)
    workflow = {"id": "wf-1", "name": "Cached"}
    versions = [{"id": "ver-1", "version": 1}]

    # Write cache files with old timestamps
    workflow_cache = cache_dir / "workflow_wf-1.json"
    workflow_cache.write_text(
        json.dumps(
            {
                "timestamp": stale_time.isoformat(),
                "payload": workflow,
            }
        ),
        encoding="utf-8",
    )

    versions_cache = cache_dir / "workflow_wf-1_versions.json"
    versions_cache.write_text(
        json.dumps(
            {
                "timestamp": stale_time.isoformat(),
                "payload": versions,
            }
        ),
        encoding="utf-8",
    )

    env_with_cache = env | {"ORCHEO_CACHE_DIR": str(cache_dir)}
    result = runner.invoke(
        app, ["--offline", "code", "scaffold", "wf-1"], env=env_with_cache
    )
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
    # With stale cache entries, should show the TTL warning
    assert "older than TTL" in result.stdout
