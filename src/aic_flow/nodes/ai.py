"""AI Agent node."""

import json
from dataclasses import dataclass, field
from typing import Any
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel
from typing_extensions import Literal
from aic_flow.graph.state import State
from aic_flow.nodes.base import AINode
from aic_flow.nodes.registry import NodeMetadata, registry


class StructuredOutput(BaseModel):
    """Structured output config for the agent."""

    type: Literal["json_schema", "json_dict", "pydantic", "typed_dict"]
    schema: str

    def get_schema_type(self) -> dict | BaseModel:
        """Get the schema type based on the schema type and content."""
        if self.type == "json_schema":
            return json.loads(self.schema)
        else:
            # Execute the schema as Python code and get the last defined object
            namespace = {}
            schema = (
                "from pydantic import BaseModel\nfrom typing_extensions import TypedDict\n"
                + self.schema
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
@dataclass
class Agent(AINode):
    """Node for executing an AI agent with tools."""

    model_config: dict
    system_prompt: str | None = None
    checkpointer: str | None = None
    tools: list[BaseTool] = field(default_factory=list)
    structured_output: dict | StructuredOutput | None = None
    """Structured output for the agent."""

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

        if type(self.structured_output) is dict:
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
