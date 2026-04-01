"""Example workflow running Claude Code as a standalone review step."""

from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.claude_code import ClaudeCodeNode


def build_graph() -> StateGraph:
    """Build a reusable Claude Code workflow."""
    graph = StateGraph(State)
    graph.add_node(
        "claude_review",
        ClaudeCodeNode(
            name="claude_review",
            prompt=(
                "Review the repository for the requested task, identify likely "
                "behavioral risks, and summarize the highest-signal findings."
            ),
            system_prompt=(
                "Do not make edits. Work only inside the provided repository and "
                "return a concise review summary suitable for operator testing."
            ),
            working_directory="{{config.configurable.working_directory}}",
            timeout_seconds=1200,
        ),
    )

    graph.add_edge(START, "claude_review")
    graph.add_edge("claude_review", END)
    return graph
