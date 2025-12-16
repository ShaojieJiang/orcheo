"""Orcheo graph example that runs an agent over MCP ChatKit widgets."""

from collections.abc import Mapping, Sequence
from typing import Any
from langchain_core.messages import ToolMessage
from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode
from orcheo.runtime.credentials import CredentialResolver, credential_resolution


DEFAULT_MODEL = "openai:gpt-4o-mini"
DEFAULT_WIDGETS_DIR = "path/to/widgets"
DEFAULT_MESSAGE = "Generate a shopping list with the following items: apples, bananas, bread, milk, eggs, cheese, butter, and tomato."  # noqa: E501


def messages_from_state(state_view: Any) -> list[Any]:
    """Return LangChain messages carried in the workflow state, if any."""
    if not isinstance(state_view, Mapping):
        return []
    messages = state_view.get("_messages") or state_view.get("messages") or []
    return messages if isinstance(messages, list) else []


def text_from_content(content: Any) -> str | None:
    """Extract text from ToolMessage content payloads."""
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence) and not isinstance(
        content, bytes | bytearray | str
    ):
        for entry in content:
            if isinstance(entry, Mapping):
                text_value = entry.get("text")
                if isinstance(text_value, str):
                    return text_value
            text_attr = getattr(entry, "text", None)
            if isinstance(text_attr, str):
                return text_attr
    return None


def widget_payload_from_tool_message(message: Any) -> Any | None:
    """Return a widget payload parsed from a ToolMessage."""
    artifact = getattr(message, "artifact", None)
    content = getattr(message, "content", None)
    if isinstance(message, Mapping):
        artifact = message.get("artifact")
        content = message.get("content")

    if isinstance(artifact, Mapping):
        structured = artifact.get("structured_content")
        if structured is not None:
            return structured

    text_value = text_from_content(content)
    if not text_value:
        return None
    return text_value.strip() or None


def print_widget_tool_messages(messages: list[Any]) -> None:
    """Print widget payloads discovered inside ToolMessages."""
    widget_payloads: list[tuple[str | None, str | None, Any]] = []
    for message in messages:
        if not (
            isinstance(message, ToolMessage)
            or (isinstance(message, Mapping) and message.get("type") == "tool")
        ):
            continue
        widget = widget_payload_from_tool_message(message)
        if widget is None:
            continue

        name = getattr(message, "name", None)
        tool_call_id = getattr(message, "tool_call_id", None)
        if isinstance(message, Mapping):
            name = message.get("name")
            tool_call_id = message.get("tool_call_id")
        widget_payloads.append((name, tool_call_id, widget))

    if not widget_payloads:
        print("  No widget payloads found in ToolMessages.")
        return

    print("  Widget payloads from ToolMessages:")
    for index, (name, tool_call_id, widget) in enumerate(widget_payloads, start=1):
        parts = []
        if name:
            parts.append(f"name={name!r}")
        if tool_call_id:
            parts.append(f"tool_call_id={tool_call_id!r}")
        header = " ".join(parts) or "<no ToolMessage metadata>"
        print(f"    [{index}] {header}")
        serialized = widget if isinstance(widget, str) else repr(widget)
        for line in serialized.splitlines() or [serialized]:
            print(f"      {line}")


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


async def run_manual_test(
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
    messages = messages_from_state(result)
    if messages:
        print_widget_tool_messages(messages)
    else:
        print("  No messages were returned in the workflow state.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_manual_test())
