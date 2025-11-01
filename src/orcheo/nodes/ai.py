"""AI Agent node."""

from __future__ import annotations
from typing import Any
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.agent_tools.registry import tool_registry
from orcheo.nodes.base import AINode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="AgentNode",
        description="Execute an AI agent with tools",
        category="ai",
    )
)
class AgentNode(AINode):
    """Node for executing an AI agent with tools."""

    model_name: str
    """Model name for the agent."""
    model_settings: dict | None = None
    """Model settings for the agent."""
    system_prompt: str | None = None
    """System prompt for the agent."""
    predefined_tools: list[str] = Field(default_factory=list)
    """Tool names predefined by Orcheo."""
    workflow_tools: list[str] = Field(default_factory=list)
    """Workflow IDs to be used as tools."""
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
            if tool is not None:
                # If it's already a BaseTool instance (e.g., from @tool
                # decorator), use it directly
                if isinstance(tool, BaseTool):
                    tools.append(tool)
                # Otherwise, assume it's a factory and call it
                else:
                    tool_instance = tool()
                    tools.append(tool_instance)
            else:
                # TODO: Log warning or raise error for unknown tool
                pass

        # TODO: get tool definitions from workflow_tools

        # Get MCP tools
        mcp_client = MultiServerMCPClient(connections=self.mcp_servers)
        mcp_tools = await mcp_client.get_tools()
        tools.extend(mcp_tools)

        return tools

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the agent and return results."""
        tools = await self._prepare_tools()

        response_format_strategy = None
        if self.response_format is not None:
            response_format_strategy = ProviderStrategy(self.response_format)  # type: ignore[arg-type]

        agent = create_agent(
            self.model_name,
            tools=tools,
            system_prompt=self.system_prompt,
            response_format=response_format_strategy,
        )
        # TODO: for models that don't support ProviderStrategy, use ToolStrategy

        # Execute agent with state as input
        result = await agent.ainvoke(state, config)  # type: ignore[arg-type]
        return result
