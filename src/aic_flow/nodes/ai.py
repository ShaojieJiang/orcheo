"""AI Agent node."""

from dataclasses import dataclass
from typing import Any
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from aic_flow.graph.state import State
from aic_flow.nodes.base import AINode
from aic_flow.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="Agent",
        description="Execute an AI agent with tools",
        category="ai",
    )
)
@dataclass
class Agent(AINode):
    """Node for executing an AI agent with tools."""

    model_config: dict
    system_prompt: str | None = None
    checkpointer: str | None = None
    # tools: list[BaseTool] # TODO: Add tools and MCP support
    # structured_output: Any # TODO: Add structured output

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the agent and return results."""
        # TODO: Prepare all the components
        model = init_chat_model(**self.model_config)
        match self.checkpointer:
            case "memory":
                checkpointer = InMemorySaver()
            # TODO: Add sqlite and postgres checkpointer
            # case "sqlite":
            #     checkpointer = SqliteSaver()
            # case "postgres":
            #     checkpointer = PostgresSaver()
            case None:
                checkpointer = None  # type: ignore
            case _:
                raise ValueError(f"Invalid checkpointer: {self.checkpointer}")

        agent = create_react_agent(
            model, [], prompt=self.system_prompt, checkpointer=checkpointer
        )

        # Execute agent with state as input
        result = await agent.ainvoke({"input": state}, config)
        return result
