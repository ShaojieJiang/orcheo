"""Standard workflow nodes covering triggers, data, and utilities."""

from __future__ import annotations
import asyncio
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal
import httpx
from pydantic import ConfigDict, Field
from RestrictedPython import compile_restricted
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import guarded_iter_unpack_sequence
from orcheo.graph.state import State
from orcheo.nodes.base import AINode, TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


_LOGGER = logging.getLogger(__name__)


def _resolve_path(payload: Mapping[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        else:
            return None
    return value


@registry.register(
    NodeMetadata(
        name="WebhookTrigger",
        description="Receive external HTTP events to start a workflow.",
        category="trigger",
    )
)
class WebhookTriggerNode(TaskNode):
    """Normalize inbound webhook payloads."""

    name: str = "webhook"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Return the normalized webhook payload and headers."""
        payload = state.get("inputs", {}).get("body", {})
        headers = state.get("inputs", {}).get("headers", {})
        return {"payload": payload, "headers": headers}


@registry.register(
    NodeMetadata(
        name="CronTrigger",
        description="Fire on schedule with cron expressions.",
        category="trigger",
    )
)
class CronTriggerNode(TaskNode):
    """Emit tick data for scheduled executions."""

    name: str = "cron"
    expression: str
    timezone: str = "UTC"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Emit scheduling metadata for the cron trigger."""
        now = datetime.now(tz=UTC)
        return {
            "scheduled_at": now.isoformat(),
            "expression": self.expression,
            "timezone": self.timezone,
        }


@registry.register(
    NodeMetadata(
        name="ManualTrigger",
        description="Start a workflow manually.",
        category="trigger",
    )
)
class ManualTriggerNode(TaskNode):
    """Echo user-provided input for manual dispatch."""

    name: str = "manual"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Return manual dispatch inputs unchanged."""
        return state.get("inputs", {})


@registry.register(
    NodeMetadata(
        name="HttpPollingTrigger",
        description="Poll an HTTP endpoint for new data.",
        category="trigger",
    )
)
class HttpPollingTriggerNode(TaskNode):
    """Poll an HTTP endpoint and emit JSON responses."""

    name: str = "http_poll"
    model_config = ConfigDict(arbitrary_types_allowed=True)
    url: str
    interval_seconds: int = 60
    method: Literal["GET", "POST"] = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
    client: httpx.AsyncClient | None = None

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Fetch the remote payload using the configured polling request."""
        client = self.client or httpx.AsyncClient()
        try:
            response = await client.request(
                self.method,
                self.url,
                headers=self.headers,
                json=self.body,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if self.client is None:
                await client.aclose()
        return {"data": data, "polled_at": datetime.now(tz=UTC).isoformat()}


@registry.register(
    NodeMetadata(
        name="OpenAICompletion",
        description="Generate text completions using OpenAI models.",
        category="ai",
    )
)
class OpenAICompletionNode(AINode):
    """Call OpenAI text completion models with optional simulation."""

    name: str = "openai"
    model: str = "gpt-4o-mini"
    prompt_template: str
    simulate: bool = True

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Generate a completion either via simulation or the OpenAI API."""
        prompt = self.prompt_template.format(**state.get("inputs", {}))
        if self.simulate:
            message = f"[SIMULATED:{self.model}] {prompt}"
            return {"messages": [message]}
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        response = await client.responses.create(model=self.model, input=prompt)
        text = response.output_text
        return {"messages": [text]}


@registry.register(
    NodeMetadata(
        name="AnthropicCompletion",
        description="Call Anthropic Claude models.",
        category="ai",
    )
)
class AnthropicCompletionNode(AINode):
    """Simulate Anthropic completion responses for testing."""

    name: str = "anthropic"
    model: str = "claude-3-haiku"
    prompt: str

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Return a Claude-style completion for the provided prompt."""
        rendered = self.prompt.format(**state.get("inputs", {}))
        return {"messages": [f"[Claude:{self.model}] {rendered}"]}


@registry.register(
    NodeMetadata(
        name="TextProcessor",
        description="Apply simple text processing actions.",
        category="ai",
    )
)
class TextProcessingNode(TaskNode):
    """Apply deterministic text transformations."""

    name: str = "text_processor"
    action: Literal["uppercase", "lowercase", "title", "trim"] = "trim"
    field: str = "text"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Apply deterministic text transformations."""
        value = state.get("inputs", {}).get(self.field, "")
        if not isinstance(value, str):
            value = str(value)
        match self.action:
            case "uppercase":
                result = value.upper()
            case "lowercase":
                result = value.lower()
            case "title":
                result = value.title()
            case _:
                result = value.strip()
        return {"result": result}


@registry.register(
    NodeMetadata(
        name="HttpRequest",
        description="Make an HTTP request and return JSON response.",
        category="data",
    )
)
class HttpRequestNode(TaskNode):
    """Perform HTTP requests using httpx."""

    name: str = "http_request"
    model_config = ConfigDict(arbitrary_types_allowed=True)
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    timeout_seconds: float = 10.0
    client: httpx.AsyncClient | None = None

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Perform an HTTP request using httpx and return the response."""
        client = self.client or httpx.AsyncClient()
        try:
            response = await client.request(
                self.method,
                self.url,
                params=self.params,
                headers=self.headers,
                json=self.json_body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                payload = response.json()
            else:
                payload = response.text
        finally:
            if self.client is None:
                await client.aclose()
        return {"status": response.status_code, "body": payload}


@registry.register(
    NodeMetadata(
        name="JsonProcessor",
        description="Extract values from JSON payloads.",
        category="data",
    )
)
class JsonProcessingNode(TaskNode):
    """Extract data from JSON payloads using dotted paths."""

    name: str = "json_processor"
    source_field: str = "json"
    path: str

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Extract a value from the JSON payload using dotted notation."""
        payload = state.get("inputs", {}).get(self.source_field, {})
        if isinstance(payload, str):
            payload = json.loads(payload)
        value = _resolve_path(payload, self.path)
        return {"value": value}


@registry.register(
    NodeMetadata(
        name="DataTransform",
        description="Remap keys in structured payloads.",
        category="data",
    )
)
class DataTransformNode(TaskNode):
    """Rename keys in dictionaries using a provided mapping."""

    name: str = "data_transform"
    mapping: dict[str, str] = Field(default_factory=dict)
    source_field: str = "payload"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Remap keys in the provided payload according to the mapping."""
        payload = state.get("inputs", {}).get(self.source_field, {})
        if not isinstance(payload, Mapping):
            msg = "DataTransformNode expects a mapping payload"
            raise TypeError(msg)
        transformed = {
            self.mapping.get(key, key): value for key, value in payload.items()
        }
        return {"payload": transformed}


@registry.register(
    NodeMetadata(
        name="IfElse",
        description="Route execution depending on condition outcome.",
        category="logic",
    )
)
class IfElseNode(TaskNode):
    """Evaluate simple equality condition."""

    name: str = "if_else"
    field: str
    equals: Any

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Evaluate the configured equality condition."""
        inputs = state.get("inputs", {})
        value = _resolve_path(inputs, self.field) or inputs.get(self.field)
        branch = "true" if value == self.equals else "false"
        return {"branch": branch, "value": value}


@registry.register(
    NodeMetadata(
        name="Switch",
        description="Route execution based on mapping of values.",
        category="logic",
    )
)
class SwitchNode(TaskNode):
    """Map a value to a branch label."""

    name: str = "switch"
    field: str
    cases: dict[str, str]
    default: str = "default"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Resolve the matching branch label for the provided value."""
        value = _resolve_path(state.get("inputs", {}), self.field)
        label = self.cases.get(str(value), self.default)
        return {"branch": label, "value": value}


@registry.register(
    NodeMetadata(
        name="Merge",
        description="Merge dictionaries into a single payload.",
        category="logic",
    )
)
class MergeNode(TaskNode):
    """Merge dictionaries from inputs and results."""

    name: str = "merge"
    include_results: bool = True

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Merge input and result dictionaries for downstream nodes."""
        merged: dict[str, Any] = {}
        merged.update(state.get("inputs", {}))
        if self.include_results:
            merged.update(state.get("results", {}))
        return {"payload": merged}


@registry.register(
    NodeMetadata(
        name="SetVariable",
        description="Store a constant value in the workflow context.",
        category="logic",
    )
)
class SetVariableNode(TaskNode):
    """Set a variable for downstream nodes."""

    name: str = "set_variable"
    key: str
    value: Any

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Store the configured value under the requested key."""
        return {self.key: self.value}


@registry.register(
    NodeMetadata(
        name="PostgresQuery",
        description="Execute a SQL query against PostgreSQL.",
        category="storage",
    )
)
class PostgresQueryNode(TaskNode):
    """Simulate PostgreSQL query execution."""

    name: str = "postgres_query"
    sql: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Simulate execution of a PostgreSQL query."""
        return {"sql": self.sql, "parameters": self.parameters, "executed": True}


@registry.register(
    NodeMetadata(
        name="SQLiteQuery",
        description="Execute SQL against SQLite database.",
        category="storage",
    )
)
class SQLiteQueryNode(TaskNode):
    """Simulate SQLite query execution for unit tests."""

    name: str = "sqlite_query"
    sql: str

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Simulate execution of a SQLite query."""
        return {"sql": self.sql, "rows": []}


@registry.register(
    NodeMetadata(
        name="EmailDispatch",
        description="Send transactional emails via providers.",
        category="communication",
    )
)
class EmailDispatchNode(TaskNode):
    """Pretend to send an email and log metadata."""

    name: str = "email"
    to: list[str]
    subject: str
    body: str

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Log and return metadata about the dispatched email."""
        _LOGGER.info("Email dispatched to %s with subject %s", self.to, self.subject)
        return {"recipients": self.to, "subject": self.subject, "body": self.body}


@registry.register(
    NodeMetadata(
        name="PythonSandbox",
        description="Execute Python snippets in a sandboxed environment.",
        category="utility",
    )
)
class PythonSandboxNode(TaskNode):
    """Execute Python expression using RestrictedPython."""

    name: str = "python_sandbox"
    code: str

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Execute sandboxed Python code returning local variables."""
        compiled = compile_restricted(self.code, "<sandbox>", "exec")
        environment: dict[str, Any] = {
            "__builtins__": {
                "len": len,
                "sum": sum,
                "sorted": sorted,
                "enumerate": enumerate,
            },
            "state": state.get("inputs", {}),
            "_getiter_": default_guarded_getiter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_getitem_": default_guarded_getitem,
        }
        locals_dict: dict[str, Any] = {}
        exec(compiled, environment, locals_dict)
        return {"locals": locals_dict}


@registry.register(
    NodeMetadata(
        name="JavaScriptSandbox",
        description="Evaluate simple JavaScript expressions.",
        category="utility",
    )
)
class JavaScriptSandboxNode(TaskNode):
    """Evaluate small JavaScript expressions via Python translation."""

    name: str = "javascript_sandbox"
    expression: str
    input_field: str = "value"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Evaluate a minimal JavaScript expression safely."""
        source = self.expression.strip()
        if source.startswith("return"):
            source = source.removeprefix("return").strip()
        if source.endswith(";"):
            source = source[:-1]
        context = state.get("inputs", {}).get(self.input_field)
        math_namespace = {
            "abs": abs,
            "ceil": lambda value: int(value) if int(value) == value else int(value) + 1,
            "floor": lambda value: int(value),
            "round": round,
        }
        environment = {"input": context, "Math": math_namespace}
        result = eval(source, {"__builtins__": {}}, environment)
        return {"result": result}


@registry.register(
    NodeMetadata(
        name="Delay",
        description="Delay execution for a configurable duration.",
        category="utility",
    )
)
class DelayNode(TaskNode):
    """Sleep for the specified amount of seconds."""

    name: str = "delay"
    seconds: float = 1.0

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Pause execution for the configured number of seconds."""
        await asyncio.sleep(self.seconds)
        return {"delayed": self.seconds}


@registry.register(
    NodeMetadata(
        name="Debug",
        description="Log debugging information during workflow runs.",
        category="utility",
    )
)
class DebugNode(TaskNode):
    """Log contextual information for troubleshooting."""

    name: str = "debug"
    message: str = ""

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Log the provided debug message and return context."""
        _LOGGER.debug("Debug node executed: %s", self.message)
        return {"message": self.message, "state": state.get("inputs", {})}


@registry.register(
    NodeMetadata(
        name="SubWorkflow",
        description="Invoke a nested workflow by slug.",
        category="utility",
    )
)
class SubWorkflowNode(TaskNode):
    """Invoke a nested workflow and return its identifier."""

    name: str = "sub_workflow"
    workflow_slug: str

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Report the identifier of the invoked sub-workflow."""
        return {"invoked_workflow": self.workflow_slug}


@registry.register(
    NodeMetadata(
        name="Guardrails",
        description="Evaluate outputs against quality rules.",
        category="quality",
    )
)
class GuardrailsNode(TaskNode):
    """Evaluate heuristics for workflow guardrails."""

    name: str = "guardrails"
    field: str = "result"
    max_length: int = 1000

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Evaluate the guardrail condition for the provided text."""
        value = state.get("inputs", {}).get(self.field, "")
        length = len(value) if isinstance(value, str) else 0
        passed = length <= self.max_length
        return {"passed": passed, "length": length, "max_length": self.max_length}


__all__ = [
    "WebhookTriggerNode",
    "CronTriggerNode",
    "ManualTriggerNode",
    "HttpPollingTriggerNode",
    "OpenAICompletionNode",
    "AnthropicCompletionNode",
    "TextProcessingNode",
    "HttpRequestNode",
    "JsonProcessingNode",
    "DataTransformNode",
    "IfElseNode",
    "SwitchNode",
    "MergeNode",
    "SetVariableNode",
    "PostgresQueryNode",
    "SQLiteQueryNode",
    "EmailDispatchNode",
    "PythonSandboxNode",
    "JavaScriptSandboxNode",
    "DelayNode",
    "DebugNode",
    "SubWorkflowNode",
    "GuardrailsNode",
]
