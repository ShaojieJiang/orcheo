"""AI Agent node."""

from __future__ import annotations
import asyncio
import logging
from collections.abc import Mapping
from typing import Any
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema
from orcheo.graph.state import State
from orcheo.nodes.agent_tools.registry import tool_registry
from orcheo.nodes.base import AINode
from orcheo.nodes.registry import NodeMetadata, registry


logger = logging.getLogger(__name__)


def _create_workflow_tool_func(
    compiled_graph: Runnable,
    name: str,
    description: str,
    args_schema: type[BaseModel] | None,
) -> StructuredTool:
    """Create a StructuredTool from a compiled workflow graph.

    This factory function properly binds the compiled_graph to avoid
    closure issues in loops.

    Args:
        compiled_graph: Compiled LangGraph runnable
        name: Tool name
        description: Tool description
        args_schema: Optional Pydantic model for tool arguments

    Returns:
        StructuredTool instance wrapping the workflow
    """

    async def workflow_coroutine(**kwargs: Any) -> Any:
        """Execute the workflow graph asynchronously."""
        return await compiled_graph.ainvoke(kwargs)

    def workflow_sync(**kwargs: Any) -> Any:
        """Execute the workflow graph synchronously."""
        return asyncio.run(compiled_graph.ainvoke(kwargs))

    return StructuredTool.from_function(
        func=workflow_sync,
        coroutine=workflow_coroutine,
        name=name,
        description=description,
        args_schema=args_schema,
    )


class WorkflowTool(BaseModel):
    """Workflow tool."""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    """Name of the tool."""
    description: str
    """Description of the tool."""
    graph: SkipJsonSchema[StateGraph]
    """Workflow to be used as tool."""
    args_schema: type[BaseModel] | None = None
    """Input schema for the tool."""
    _compiled_graph: SkipJsonSchema[Runnable | None] = None
    """Cached compiled graph to avoid recompilation."""

    def get_compiled_graph(self) -> Runnable:
        """Get or compile the graph, caching the result.

        Returns:
            Compiled graph runnable
        """
        if self._compiled_graph is None:
            self._compiled_graph = self.graph.compile()
        return self._compiled_graph


@registry.register(
    NodeMetadata(
        name="AgentNode",
        description="Execute an AI agent with tools",
        category="ai",
    )
)
class AgentNode(AINode):
    """Node for executing an AI agent with tools."""

    ai_model: str
    """Identifier of the AI chat model to use."""
    model_settings: dict | None = None
    """TODO: Implement model settings for the agent."""
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional keyword arguments passed to init_chat_model.",
    )
    """Additional keyword arguments passed to init_chat_model."""
    system_prompt: str | None = None
    """System prompt for the agent."""
    predefined_tools: list[str] = Field(default_factory=list)
    """Tool names predefined by Orcheo."""
    workflow_tools: list[WorkflowTool] = Field(default_factory=list)
    """Workflows to be used as tools."""
    mcp_servers: dict[str, Any] = Field(default_factory=dict)
    """MCP servers to be used as tools (Connection from langchain_mcp_adapters)."""
    response_format: dict | type[BaseModel] | None = None

    """Response format for the agent."""

    async def _prepare_tools(self) -> list[BaseTool]:
        """Prepare the tools for the agent."""
        tools: list[BaseTool] = []

        # Resolve predefined tools from the tool registry
        for tool_name in self.predefined_tools:
            tool = tool_registry.get_tool(tool_name)
            if tool is None:
                logger.warning("Tool '%s' not found in registry, skipping", tool_name)
                continue

            # If it's already a BaseTool instance (e.g., from @tool
            # decorator), use it directly
            if isinstance(tool, BaseTool):
                tools.append(tool)
            # Otherwise, check if it's a callable factory
            elif callable(tool):
                try:
                    tool_instance = tool()
                    if not isinstance(tool_instance, BaseTool):
                        logger.error(
                            "Tool factory '%s' did not return a BaseTool instance, "
                            "got %s",
                            tool_name,
                            type(tool_instance).__name__,
                        )
                        continue
                    tools.append(tool_instance)
                except Exception as e:
                    logger.error(
                        "Failed to instantiate tool '%s': %s", tool_name, str(e)
                    )
                    continue
            else:
                logger.error(
                    "Tool '%s' is neither a BaseTool instance nor a callable factory, "
                    "got %s",
                    tool_name,
                    type(tool).__name__,
                )
                continue

        for wf_tool_def in self.workflow_tools:
            # Use cached compiled graph to avoid recompilation on every run
            compiled_graph = wf_tool_def.get_compiled_graph()

            # Create tool using factory function to properly bind variables
            # and avoid closure memory leak issues
            tool = _create_workflow_tool_func(
                compiled_graph=compiled_graph,
                name=wf_tool_def.name,
                description=wf_tool_def.description,
                args_schema=wf_tool_def.args_schema,
            )
            tools.append(tool)

        # Get MCP tools
        mcp_client = MultiServerMCPClient(connections=self.mcp_servers)
        mcp_tools = await mcp_client.get_tools()
        tools.extend(mcp_tools)

        return tools

    def _messages_from_inputs(self, inputs: Mapping[str, Any]) -> list[BaseMessage]:
        """Build LangChain messages from ChatKit-style inputs."""
        history = inputs.get("history")
        messages: list[BaseMessage] = []

        if isinstance(history, list):
            for turn in history:
                if not isinstance(turn, Mapping):
                    continue
                content = turn.get("content")
                role = turn.get("role")
                if not isinstance(content, str) or not content.strip():
                    continue
                if role == "assistant":
                    messages.append(AIMessage(content=content))
                elif role == "user":  # pragma: no branch
                    messages.append(HumanMessage(content=content))

        message_value = (
            inputs.get("message")
            or inputs.get("user_message")
            or inputs.get("query")
            or inputs.get("prompt")
        )
        if (
            isinstance(message_value, str) and message_value.strip()
        ):  # pragma: no branch
            messages.append(HumanMessage(content=message_value.strip()))

        return messages

    def _normalize_messages(self, messages: Any) -> list[BaseMessage]:
        """Normalize caller-provided messages into LangChain BaseMessages."""
        normalized: list[BaseMessage] = []
        if not isinstance(messages, list):
            return normalized

        for message in messages:
            if isinstance(message, BaseMessage):
                normalized.append(message)
                continue
            if not isinstance(message, Mapping):
                continue
            content = message.get("content")
            role = message.get("role")
            if not isinstance(content, str) or not content.strip():
                continue
            if role == "assistant":
                normalized.append(AIMessage(content=content))
            else:
                normalized.append(HumanMessage(content=content))

        return normalized

    def _build_messages(self, state: State) -> list[BaseMessage]:
        """Construct the message list for the agent invocation."""
        existing_messages = self._normalize_messages(state.get("messages"))
        if existing_messages:
            return existing_messages

        inputs = state.get("inputs", {}) if isinstance(state, Mapping) else {}
        return self._messages_from_inputs(inputs)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the agent and return results."""
        tools = await self._prepare_tools()

        response_format_strategy = None
        if self.response_format is not None:
            response_format_strategy = ProviderStrategy(self.response_format)  # type: ignore[arg-type]

        # Initialize chat model with model_kwargs
        model = init_chat_model(self.ai_model, **self.model_kwargs)
        agent = create_agent(
            model,
            tools=tools,
            system_prompt=self.system_prompt,
            response_format=response_format_strategy,
        )
        # TODO: for models that don't support ProviderStrategy, use ToolStrategy

        messages = self._build_messages(state)
        # Execute agent with normalized messages as input
        payload: dict[str, Any] = {"messages": messages}
        result = await agent.ainvoke(payload, config)  # type: ignore[arg-type]
        return result
