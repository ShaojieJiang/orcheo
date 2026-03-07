"""Workflow download CLI tests for removed auto/json formats."""

from __future__ import annotations
import re
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.main import app


VERSION = {
    "id": "ver-1",
    "version": 1,
    "graph": {
        "format": "langgraph-script",
        "source": "from langgraph.graph import StateGraph\n",
        "entrypoint": None,
        "index": {"cron": []},
    },
}
ANSI_ESCAPE_PATTERN = re.compile("\x1b\\[[0-9;]*m")


def test_workflow_download_rejects_removed_format_option(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(
        app,
        ["workflow", "download", "wf-1", "--format", "auto"],
        env=env,
    )
    assert result.exit_code == 2
    clean_output = ANSI_ESCAPE_PATTERN.sub("", result.output)
    assert "no such option" in clean_output.lower()
    assert "--format" in clean_output


def test_workflow_download_with_cache_notice(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Cached downloads continue to work for python output."""
    workflow = {"id": "wf-1", "name": "LangGraphWorkflow"}

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=[VERSION])
        )
        first = runner.invoke(app, ["workflow", "download", "wf-1"], env=env)
        assert first.exit_code == 0

    result = runner.invoke(app, ["--offline", "workflow", "download", "wf-1"], env=env)
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
