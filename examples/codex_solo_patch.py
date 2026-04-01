"""Example workflow running Codex as a standalone implementation step."""

from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.codex import CodexNode


def build_graph() -> StateGraph:
    """Build a reusable Codex workflow."""
    graph = StateGraph(State)
    graph.add_node(
        "codex_patch",
        CodexNode(
            name="codex_patch",
            prompt=(
                "Implement the requested repository change, prefer targeted tests, "
                "and report the exact files touched."
            ),
            system_prompt=(
                "Keep edits minimal and production-ready. Avoid broad refactors unless "
                "they are strictly required by the task."
            ),
            working_directory="{{config.configurable.working_directory}}",
            timeout_seconds=1800,
        ),
    )

    graph.add_edge(START, "codex_patch")
    graph.add_edge("codex_patch", END)
    return graph
