"""Workflow list CLI command tests."""

from __future__ import annotations
import httpx
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def test_workflow_list_renders_table(runner: CliRunner, env: dict[str, str]) -> None:
    payload = [{"id": "wf-1", "name": "Demo", "slug": "demo", "is_archived": False}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list"], env=env)
    assert result.exit_code == 0
    assert "Demo" in result.stdout
    assert "Share URL" in result.stdout


def test_workflow_list_excludes_archived_by_default(
    runner: CliRunner, env: dict[str, str]
) -> None:
    payload = [{"id": "wf-1", "name": "Active", "slug": "active", "is_archived": False}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list"], env=env)
    assert result.exit_code == 0
    assert "Active" in result.stdout


def test_workflow_list_includes_archived_with_flag(
    runner: CliRunner, env: dict[str, str]
) -> None:
    payload = [
        {"id": "wf-1", "name": "Active", "slug": "active", "is_archived": False},
        {"id": "wf-2", "name": "Archived", "slug": "archived", "is_archived": True},
    ]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows?include_archived=true").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list", "--archived"], env=env)
    assert result.exit_code == 0
    assert "Active" in result.stdout
    assert "Archived" in result.stdout


def test_workflow_list_uses_cache_notice(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test that workflow list shows cache notice when using cached data."""
    payload = [{"id": "wf-1", "name": "Demo", "slug": "demo", "is_archived": False}]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        # First call to populate cache
        first = runner.invoke(app, ["workflow", "list"], env=env)
        assert first.exit_code == 0

    # Second call in offline mode should use cache
    result = runner.invoke(app, ["--offline", "workflow", "list"], env=env)
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
