"""Workflow tool progress update tests."""

from __future__ import annotations
from typing import Any
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.agent_tools.context import (
    tool_execution_context,
    tool_progress_context,
)
from orcheo.nodes.ai import WorkflowTool, _create_workflow_tool_func


def _build_tool_graph() -> StateGraph:
    graph = StateGraph(State)

    def node_a(_state: State) -> dict[str, Any]:
        return {"results": {"node_a": {"ok": True}}}

    def node_b(_state: State) -> dict[str, Any]:
        return {"results": {"node_b": {"ok": True}}}

    graph.add_node("node_a", node_a)
    graph.add_node("node_b", node_b)
    graph.add_edge(START, "node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    return graph


@pytest.mark.asyncio
async def test_workflow_tool_emits_progress_updates() -> None:
    tool_graph = _build_tool_graph()
    tool_def = WorkflowTool(
        name="tool_graph",
        description="Test tool graph",
        graph=tool_graph,
    )
    compiled_graph = tool_def.get_compiled_graph()
    tool = _create_workflow_tool_func(
        compiled_graph=compiled_graph,
        name=tool_def.name,
        description=tool_def.description,
        args_schema=None,
    )

    updates: list[dict[str, Any]] = []

    async def progress_callback(step: dict[str, Any]) -> None:
        updates.append(step)

    config: RunnableConfig = {"configurable": {"thread_id": "tool-test"}}

    with tool_execution_context(config), tool_progress_context(progress_callback):
        result = await tool.coroutine()

    assert result
    assert updates
    assert any("node_a" in step for step in updates)
    assert any("node_b" in step for step in updates)
