"""Workflow download CLI tests for auto format logic."""

from __future__ import annotations
import json
import httpx
import respx
from orcheo_sdk.cli.main import app
from typer.testing import CliRunner


def test_workflow_download_auto_format_langgraph_script(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test download with auto format: LangGraph script downloads as Python."""
    original_source = """from langgraph.graph import StateGraph

def my_node(state):
    return state

graph = StateGraph(dict)
graph.add_node("my_node", my_node)
"""
    workflow = {"id": "wf-1", "name": "LangGraphWorkflow"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "format": "langgraph-script",
                "source": original_source,
                "entrypoint": None,
                "summary": {"nodes": [{"name": "my_node"}], "edges": []},
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],  # No --format, should default to auto
            env=env,
        )
    assert result.exit_code == 0
    # Should output Python code (not JSON)
    assert "from langgraph.graph import StateGraph" in result.stdout
    assert "def my_node(state)" in result.stdout
    # Should NOT contain JSON structure
    assert '"name"' not in result.stdout


def test_workflow_download_auto_format_sdk_workflow(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download with auto format for SDK workflow downloads as JSON."""
    workflow = {"id": "wf-1", "name": "SDKWorkflow"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                # No "format" field or format is not "langgraph-script"
                "nodes": [{"name": "node1", "type": "Agent"}],
                "edges": [],
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],  # No --format, should default to auto
            env=env,
        )
    assert result.exit_code == 0
    # Should output JSON (not Python code)
    output = json.loads(result.stdout)
    assert output["name"] == "SDKWorkflow"
    assert "graph" in output


def test_workflow_download_auto_format_missing_graph(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Gracefully handle workflows whose versions lack a graph payload."""
    workflow = {"id": "wf-1", "name": "SDKWorkflow"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            # Older versions may omit the "graph" field altogether.
            # The CLI should fall back to JSON output without crashing.
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],  # No --format, should default to auto
            env=env,
        )
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["name"] == "SDKWorkflow"
    assert output["graph"] == {}


def test_workflow_download_auto_format_explicit(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download with explicit --format auto for LangGraph script."""
    original_source = "from langgraph.graph import StateGraph\n"
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {
                "format": "langgraph-script",
                "source": original_source,
                "entrypoint": None,
                "summary": {"nodes": [], "edges": []},
            },
        }
    ]

    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        result = runner.invoke(
            app,
            ["workflow", "download", "wf-1", "--format", "auto"],
            env=env,
        )
    assert result.exit_code == 0
    # Should output Python code
    assert original_source in result.stdout


def test_workflow_download_with_cache_notice(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download shows cache notice when using cached data."""
    workflow = {"id": "wf-1", "name": "Test"}
    versions = [
        {
            "id": "ver-1",
            "version": 1,
            "graph": {"nodes": [{"id": "a"}], "edges": []},
        }
    ]

    # First call to populate cache
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        first = runner.invoke(
            app,
            ["workflow", "download", "wf-1"],
            env=env,
        )
        assert first.exit_code == 0

    # Second call in offline mode should use cache and show notice
    result = runner.invoke(
        app,
        ["--offline", "workflow", "download", "wf-1"],
        env=env,
    )
    assert result.exit_code == 0
    assert "Using cached data" in result.stdout
