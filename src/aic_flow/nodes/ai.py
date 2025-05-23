"""AI Agent node."""

import json
from dataclasses import field
from typing import Annotated, Any, Literal
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import InjectedState, create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from pydantic import BaseModel
from aic_flow.graph.state import State
from aic_flow.nodes.base import AINode
from aic_flow.nodes.registry import NodeMetadata, registry


class StructuredOutput(BaseModel):
    """Structured output config for the agent."""

    type: Literal["json_schema", "json_dict", "pydantic", "typed_dict"]
    schema_str: str

    def get_schema_type(self) -> dict | BaseModel:
        """Get the schema type based on the schema type and content."""
        if self.type == "json_schema":
            return json.loads(self.schema_str)
        else:
            # Execute the schema as Python code and get the last defined object
            namespace = {}
            schema = (
                "from pydantic import BaseModel\n"
                + "from typing_extensions import TypedDict\n"
                + self.schema_str
            )
            exec(schema, namespace)
            return list(namespace.values())[-1]


@registry.register(
    NodeMetadata(
        name="Agent",
        description="Execute an AI agent with tools",
        category="ai",
    )
)
class Agent(AINode):
    """Node for executing an AI agent with tools."""

    description: str = "Execute an AI agent with tools"
    model_settings: dict
    """Model settings for the agent."""
    system_prompt: str | None = None
    """System prompt for the agent."""
    checkpointer: str | None = None
    """Checkpointer used to save the agent's state."""
    tools: list[BaseTool] = field(default_factory=list)
    """Tools used by the agent."""
    structured_output: dict | StructuredOutput | None = None
    """Structured output for the agent."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the agent and return results."""
        # TODO: Prepare all the components
        model = init_chat_model(**self.model_settings)
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

        if isinstance(self.structured_output, dict):
            structured_output = StructuredOutput(**self.structured_output)
        response_format = (
            None
            if self.structured_output is None
            else structured_output.get_schema_type()
        )

        agent = create_react_agent(
            model.bind_tools(self.tools),
            tools=self.tools,
            prompt=self.system_prompt,
            response_format=response_format,
            checkpointer=checkpointer,
        )

        # Execute agent with state as input
        result = await agent.ainvoke(state, config)
        return result

    def _run(
        self,
        state: Annotated[AgentState, InjectedState],
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """Execute the agent and return results."""
        pass  # TODO: implement when using agent as a tool
