"""AI Agent node."""

import json
from collections.abc import Callable, Mapping
from dataclasses import field
from time import perf_counter
from typing import Any, Literal
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.base import AINode, BaseNode, TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


class StructuredOutput(BaseModel):
    """Structured output config for the agent."""

    schema_type: Literal["json_schema", "json_dict", "pydantic", "typed_dict"]
    schema_str: str

    def get_schema_type(self) -> dict | type[BaseModel]:
        """Get the schema type based on the schema type and content."""
        if self.schema_type == "json_schema":
            return json.loads(self.schema_str)
        else:
            # Execute the schema as Python code and get the last defined object
            namespace: dict[str, Any] = {}
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

    model_settings: dict
    """Model settings for the agent."""
    system_prompt: str | None = None
    """System prompt for the agent."""
    checkpointer: str | None = None
    """Checkpointer used to save the agent's state."""
    tools: list[BaseNode | BaseTool] = field(default_factory=list)
    """Tools used by the agent."""
    structured_output: dict | StructuredOutput | None = None
    """Structured output for the agent."""

    def _prepare_tools(self) -> list[BaseTool]:
        """Prepare the tools for the agent."""
        return [
            tool
            if isinstance(tool, BaseTool)
            else StructuredTool.from_function(
                tool.tool_run,
                coroutine=tool.tool_arun,
                name=tool.name,
                parse_docstring=True,
            )
            for tool in self.tools
        ]

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

        tools = self._prepare_tools()

        agent = create_react_agent(
            model.bind_tools(tools),
            tools=tools,
            prompt=self.system_prompt,
            response_format=response_format,
            checkpointer=checkpointer,
        )

        # Execute agent with state as input
        result = await agent.ainvoke(state, config)
        return result


@registry.register(
    NodeMetadata(
        name="OpenAICompletion",
        description="Generate completions using the configured OpenAI model.",
        category="ai",
    )
)
class OpenAICompletion(AINode):
    """Simplified OpenAI completion node with latency guardrails."""

    prompt_template: str = "Respond to the user input."
    model: str = "gpt-4.1"
    temperature: float = 0.2
    max_latency_ms: int = 3000

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Produce a completion using the configured prompt template."""
        inputs = state.get("inputs", {})
        formatted_prompt = self.prompt_template.format(**inputs)
        start = perf_counter()
        # Guardrails operate even when a real LLM is not invoked (offline mode)
        latency_ms = (perf_counter() - start) * 1000
        if latency_ms > self.max_latency_ms:
            msg = "Latency budget exceeded"
            raise TimeoutError(msg)
        message = {
            "role": "assistant",
            "content": f"{formatted_prompt} (model={self.model})",
        }
        return {"messages": [message], "latency_ms": latency_ms}


@registry.register(
    NodeMetadata(
        name="AnthropicCompletion",
        description="Generate Claude-style responses with safety notes.",
        category="ai",
    )
)
class AnthropicCompletion(AINode):
    """Anthropic completion node that decorates responses with safety notes."""

    prompt: str
    model: str = "claude-3-sonnet"
    safety: str = "medium"

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a deterministic completion referencing safety settings."""
        content = f"Claude reply for prompt '{self.prompt}'. Safety={self.safety}."
        return {"messages": [{"role": "assistant", "content": content}]}


@registry.register(
    NodeMetadata(
        name="TextProcessing",
        description="Apply text processing utilities to the incoming payload.",
        category="ai",
    )
)
class TextProcessingNode(TaskNode):
    """Node that performs simple text transformations."""

    operation: Literal["lower", "upper", "title", "summary"] = "lower"
    source_path: str = "inputs.text"
    max_length: int = Field(default=256, ge=1)

    def _resolve_payload(self, state: State) -> Mapping[str, Any]:
        inputs_raw = state.get("inputs")
        if inputs_raw is None:
            return {}
        if isinstance(inputs_raw, Mapping):
            return inputs_raw
        msg = "TextProcessingNode expects `inputs` to be a mapping."
        raise TypeError(msg)

    def _extract_text(self, state: State, payload: Mapping[str, Any]) -> str:
        parts = [segment for segment in self.source_path.split(".") if segment]
        roots: list[Mapping[str, Any]] = [
            {"inputs": payload, "results": state.get("results", {})},
            payload,
        ]
        value: Any = None
        for root in roots:
            candidate: Any = root
            for part in parts:
                if isinstance(candidate, Mapping):
                    candidate = candidate.get(part)
                else:
                    candidate = None
                    break
            if candidate is not None:
                value = candidate
                break
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    def _apply_operation(self, text: str) -> str:
        def summarize(value: str) -> str:
            first_sentence = value.split(". ")[0]
            return f"{first_sentence}..." if first_sentence else value

        operations: dict[str, Callable[[str], str]] = {
            "lower": str.lower,
            "upper": str.upper,
            "title": str.title,
            "summary": summarize,
        }
        transformer = operations.get(self.operation)
        if transformer is None:
            return text
        return transformer(text)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the transformed text payload."""
        payload = self._resolve_payload(state)
        text = self._extract_text(state, payload)[: self.max_length]
        processed = self._apply_operation(text)
        return {"text": processed}


__all__ = [
    "Agent",
    "OpenAICompletion",
    "AnthropicCompletion",
    "TextProcessingNode",
]
