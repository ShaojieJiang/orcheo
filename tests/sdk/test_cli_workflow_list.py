"""Workflow list CLI command tests."""

from __future__ import annotations
import httpx
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def test_workflow_list_renders_table(runner: CliRunner, env: dict[str, str]) -> None:
    payload = [
        {
            "id": "wf-1",
            "name": "Demo",
            "is_archived": False,
            "is_public": True,
            "require_login": False,
            "published_at": "2024-01-01T00:00:00Z",
        }
    ]
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(app, ["workflow", "list"], env=env)
    assert result.exit_code == 0
    assert "Demo" in result.stdout
    assert "Public" in result.stdout
    assert "http://api.test/chat/wf-1" in result.stdout


def test_workflow_list_excludes_archived_by_default(
    runner: CliRunner, env: dict[str, str]
) -> None:
    payload = [
        {
            "id": "wf-1",
            "name": "Active",
            "is_archived": False,
            "is_public": False,
            "require_login": False,
        }
    ]
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
        {
            "id": "wf-1",
            "name": "Active",
            "is_archived": False,
            "is_public": False,
            "require_login": False,
        },
        {
            "id": "wf-2",
            "name": "Archived",
            "is_archived": True,
            "is_public": False,
            "require_login": False,
        },
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
