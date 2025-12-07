"""Production-Ready Pipeline demo - placeholder for future implementation."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode


# Default configuration inlined for server execution
DEFAULT_CONFIG: dict[str, Any] = {
    "production": {
        "caching": {
            "enabled": True,
            "cache_ttl_seconds": 3600,
            "similarity_threshold": 0.92,
        },
        "streaming": {"enabled": True, "buffer_size": 10},
        "guardrails": {
            "hallucination": {"method": "llm_judge", "threshold": 0.8},
            "policy_compliance": {"filters": ["pii", "toxicity"]},
        },
    },
    "session_management": {
        "max_concurrent_sessions": 100,
        "session_timeout_minutes": 30,
    },
}


class PlaceholderMessageNode(TaskNode):
    """Simple placeholder TaskNode until the production pipeline is ready."""

    message: str = Field(description="Placeholder message shown to the user")

    async def run(self, _state: State, _config: RunnableConfig) -> dict[str, Any]:
        """Return the placeholder response while the workflow is under development."""
        return {"outputs": {"message": self.message}}


async def build_graph() -> StateGraph:
    """Entrypoint for the Orcheo server to load the graph.

    This is a placeholder implementation. The full production workflow will
    include caching, guardrails, streaming, and session management.
    """
    workflow = StateGraph(State)

    placeholder = PlaceholderMessageNode(
        name="placeholder",
        message="Demo 4: Production-Ready Pipeline - Coming Soon",
    )

    workflow.add_node("placeholder", placeholder)
    workflow.set_entry_point("placeholder")
    workflow.add_edge("placeholder", END)

    return workflow
