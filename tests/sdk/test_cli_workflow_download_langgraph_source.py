"""Workflow download CLI tests for LangGraph source handling."""

from __future__ import annotations
import httpx
import respx
from typer.testing import CliRunner
from orcheo_sdk.cli.main import app


def test_workflow_download_langgraph_script_returns_original_source(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Test workflow download returns original LangGraph script source."""
    original_source = """from langgraph.graph import StateGraph
from typing import TypedDict

class State(TypedDict):
    messages: list[str]

def my_node(state: State) -> State:
    return {"messages": state["messages"] + ["processed"]}

graph = StateGraph(State)
graph.add_node("my_node", my_node)
graph.set_entry_point("my_node")
graph.set_finish_point("my_node")
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
                "index": {"cron": []},
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
        result = runner.invoke(app, ["workflow", "download", "wf-1"], env=env)
    assert result.exit_code == 0
    assert "from langgraph.graph import StateGraph" in result.stdout
    assert "def my_node(state: State)" in result.stdout
    # Should NOT contain SDK template code
    assert "from orcheo_sdk import Workflow" not in result.stdout
