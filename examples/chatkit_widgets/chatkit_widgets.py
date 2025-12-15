"""Orcheo graph example that runs an agent over MCP ChatKit widgets."""

from __future__ import annotations
from typing import Any
from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode
from orcheo.runtime.credentials import CredentialResolver, credential_resolution


DEFAULT_MODEL = "openai:gpt-4o-mini"
DEFAULT_WIDGETS_DIR = "path/to/widgets"
DEFAULT_MESSAGE = "Generate a shopping list with the following items: apples, bananas, bread, milk, eggs, cheese, butter, and tomato."  # noqa: E501


def build_graph(
    model: str = DEFAULT_MODEL,
    widgets_dir: str = DEFAULT_WIDGETS_DIR,
) -> StateGraph:
    """Return a graph that routes all work through the ChatKit agent node."""
    mcp_servers = {
        "mcp-chatkit-widget": {
            "transport": "stdio",
            "command": "uvx",
            "args": ["mcp-chatkit-widget", "--widgets-dir", widgets_dir],
        }
    }
    agent_node = AgentNode(
        name="agent",
        ai_model=model,
        model_kwargs={"api_key": "[[openai_api_key]]"},
        system_prompt="You are a helpful assistant that can use widget tools to interact with the user.",  # noqa: E501
        mcp_servers=mcp_servers,
    )

    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph


def setup_credentials() -> CredentialResolver:
    """Return a credential resolver connected to the local vault."""
    from orcheo_backend.app.dependencies import get_vault

    vault = get_vault()
    return CredentialResolver(vault)


async def _run_manual_test(
    *,
    model: str = DEFAULT_MODEL,
    widgets_dir: str = DEFAULT_WIDGETS_DIR,
    message: str = DEFAULT_MESSAGE,
    resolver: CredentialResolver | None = None,
) -> None:
    """Compile the widget graph and run it once with credential placeholders."""
    workflow = build_graph(model=model, widgets_dir=widgets_dir).compile()
    resolver = resolver or setup_credentials()

    payload: dict[str, Any] = {"messages": [{"content": message, "role": "user"}]}

    print("Running ChatKit widgets manual test")
    print(f"Using widgets dir: {widgets_dir!r}")
    print(f"Prompt: {message!r}")

    with credential_resolution(resolver):
        result = await workflow.ainvoke(payload)  # type: ignore[arg-type]

    print("Manual test results:")
    results = result.get("results") or {}
    nodes = ", ".join(sorted(results.keys())) or "<no results>"
    print(f"  Results nodes: {nodes}")
    agent_result = results.get("agent")
    if agent_result:
        print(f"  Agent output keys: {', '.join(sorted(agent_result.keys()))}")
        print(f"  Agent excerpt: {agent_result!r}")
    else:
        print("  Agent node did not emit any structured output")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_run_manual_test())
