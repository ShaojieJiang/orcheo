"""Utility oriented nodes used across Orcheo workflows."""

from __future__ import annotations
import copy
import json
import logging
import warnings
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from RestrictedPython import compile_restricted


if TYPE_CHECKING:
    pass
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safe_builtins,
    safer_getattr,
)
from RestrictedPython.PrintCollector import PrintCollector
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


logger = logging.getLogger(__name__)


def _normalise_state_snapshot(state: State) -> dict[str, Any]:
    """Return a serialisable snapshot of ``state`` for debugging."""
    inputs = {}
    if isinstance(state.get("inputs"), Mapping):
        inputs = dict(state["inputs"])

    results = {}
    if isinstance(state.get("results"), Mapping):
        results = copy.deepcopy(state["results"])

    return {"inputs": inputs, "results": results}


def _extract_from_state(state: State, path: str) -> tuple[bool, Any]:
    """Return whether ``path`` exists in ``state`` and its associated value."""
    if not path:
        msg = "tap_path must be a non-empty string"
        raise ValueError(msg)

    current: Any = state.get("results", {})
    segments = [segment.strip() for segment in path.split(".") if segment.strip()]
    if not segments:
        msg = "tap_path must contain at least one segment"
        raise ValueError(msg)

    for segment in segments:
        if isinstance(current, Mapping) and segment in current:
            current = current[segment]
            continue
        if isinstance(current, Sequence) and not isinstance(current, str | bytes):
            try:
                index = int(segment)
            except ValueError:
                return False, None
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


@registry.register(
    NodeMetadata(
        name="PythonSandboxNode",
        description="Execute Python code using RestrictedPython sandboxing.",
        category="utility",
    )
)
class PythonSandboxNode(TaskNode):
    """Execute short snippets of Python with RestrictedPython safeguards."""

    source: str = Field(description="Python source executed inside the sandbox")
    bindings: dict[str, Any] = Field(
        default_factory=dict,
        description="Variables injected into the sandbox environment",
    )
    expose_state: bool = Field(
        default=False,
        description="Expose the current workflow state as 'state' inside the sandbox",
    )
    result_variable: str = Field(
        default="result",
        description="Variable name read from the sandbox after execution",
    )
    capture_stdout: bool = Field(
        default=True,
        description="Capture values printed inside the sandbox",
    )
    include_locals: bool = Field(
        default=False,
        description="Include sandbox locals in the node output",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the configured source code and return the results."""
        sandbox_globals: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "_getattr_": safer_getattr,
            "_getitem_": default_guarded_getitem,
            "_getiter_": default_guarded_getiter,
            "_write_": full_write_guard,
            "_print_": PrintCollector,
            "_unpack_sequence_": guarded_unpack_sequence,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        }

        locals_namespace = dict(self.bindings)
        if self.expose_state:
            locals_namespace["state"] = state

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=".*Prints, but never reads 'printed' variable.*",
                category=SyntaxWarning,
            )
            bytecode = compile_restricted(
                self.source, filename="<sandbox>", mode="exec"
            )
        exec(bytecode, sandbox_globals, locals_namespace)

        result = locals_namespace.get(self.result_variable)
        collector_instance = locals_namespace.get("_print")
        stdout: list[str] = []
        if isinstance(collector_instance, PrintCollector):
            captured = "".join(getattr(collector_instance, "txt", []))
            if captured:
                stdout = captured.splitlines()
        elif callable(collector_instance):
            try:
                stdout_value = collector_instance()
            except TypeError:
                stdout_value = None
            if isinstance(stdout_value, str):
                stdout = [stdout_value]
        if not self.capture_stdout:
            stdout = []

        payload: dict[str, Any] = {
            "result": result,
            "stdout": stdout,
        }
        if self.include_locals:
            payload["locals"] = {
                key: value
                for key, value in locals_namespace.items()
                if not key.startswith("__")
            }
        return payload


@registry.register(
    NodeMetadata(
        name="JavaScriptSandboxNode",
        description="Execute JavaScript using js2py sandboxing.",
        category="utility",
    )
)
class JavaScriptSandboxNode(TaskNode):
    """Evaluate JavaScript snippets via py-mini-racer."""

    script: str = Field(description="JavaScript source executed via py-mini-racer")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Variables injected into the JS runtime",
    )
    result_variable: str = Field(
        default="result",
        description="Variable exported from the runtime after execution",
    )
    capture_console: bool = Field(
        default=True,
        description="Capture console.log output for debugging",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute JavaScript and return the evaluated result."""
        from py_mini_racer import py_mini_racer

        runtime = py_mini_racer.MiniRacer()

        if self.capture_console:
            runtime.eval(
                "\n".join(
                    [
                        "var __ORCHEO_CONSOLE__ = [];",
                        "var console = {",
                        "  log: function() {",
                        "    __ORCHEO_CONSOLE__.push(",
                        "      Array.prototype.map.call(",
                        "        arguments,",
                        "        function(arg) { return String(arg); }",
                        "      ).join(' ')",
                        "    );",
                        "  }",
                        "};",
                    ]
                )
            )
        else:
            runtime.eval("var console = { log: function() {} };")

        for key, value in self.context.items():
            encoded = json.dumps(value)
            if key.isidentifier():
                runtime.eval(f"var {key} = {encoded};")
            else:
                runtime.eval(f"this[{json.dumps(key)}] = {encoded};")

        runtime.eval(self.script)

        result_name = self.result_variable
        result_expression = (
            f"(typeof {result_name} === 'undefined' ? null : {result_name})"
        )
        try:
            result_json = runtime.eval(f"JSON.stringify({result_expression})")
        except py_mini_racer.JSEvalException:
            result_value = runtime.eval(result_expression)
        else:
            result_value = None if result_json is None else json.loads(result_json)

        console_output: list[str] = []
        if self.capture_console:
            console_json = runtime.eval("JSON.stringify(__ORCHEO_CONSOLE__)")
            console_output = [] if console_json is None else json.loads(console_json)

        return {
            "result": result_value,
            "console": console_output,
        }


@registry.register(
    NodeMetadata(
        name="DebugNode",
        description="Capture state snapshots and emit debug information.",
        category="utility",
    )
)
class DebugNode(TaskNode):
    """Emit debug information without mutating workflow state."""

    message: str | None = Field(
        default=None,
        description="Optional message recorded alongside the snapshot",
    )
    tap_path: str | None = Field(
        default=None,
        description="Dotted path resolved from state['results'] for inspection",
    )
    include_state: bool = Field(
        default=False,
        description="Whether to include the state snapshot in the output",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return debugging metadata for the current execution context."""
        found = False
        tapped_value: Any = None
        if self.tap_path is not None:
            found, tapped_value = _extract_from_state(state, self.tap_path)

        log_components: list[str] = []
        if self.message:
            log_components.append(self.message)
        if self.tap_path:
            log_components.append(
                f"path={self.tap_path} found={found} value={tapped_value!r}"
            )
        if log_components:
            logger.info("DebugNode %s: %s", self.name, " | ".join(log_components))

        payload: dict[str, Any] = {
            "message": self.message,
            "tap_path": self.tap_path,
            "found": found,
            "value": tapped_value,
        }
        if self.include_state:
            payload["state"] = _normalise_state_snapshot(state)
        return payload


@registry.register(
    NodeMetadata(
        name="SubWorkflowNode",
        description="Execute a mini workflow inline using the node registry.",
        category="utility",
    )
)
class SubWorkflowNode(TaskNode):
    """Execute a series of nodes sequentially within the current workflow."""

    steps: list[Mapping[str, Any]] = Field(
        default_factory=list,
        description="Sequence of node configurations executed as a sub-workflow",
    )
    propagate_to_parent: bool = Field(
        default=False,
        description="Update the parent state with sub-workflow results",
    )
    include_state: bool = Field(
        default=False,
        description="Include the sub-workflow state in the node output",
    )
    result_step: str | None = Field(
        default=None,
        description="Optional name of the step whose result is returned",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the configured sub-workflow sequentially."""
        if not self.steps:
            return {"steps": [], "result": None}

        sub_state = State(
            {
                "inputs": dict(state.get("inputs", {})),
                "results": copy.deepcopy(state.get("results", {})),
                "messages": list(state.get("messages", [])),
            }
        )

        step_results: list[dict[str, Any]] = []
        result_lookup: dict[str, Any] = {}

        for step in self.steps:
            node_type = step.get("type")
            if not isinstance(node_type, str) or not node_type:
                msg = f"Each step must define a non-empty type: {step!r}"
                raise ValueError(msg)

            node_class = registry.get_node(node_type)
            if node_class is None:
                msg = f"Unknown node type {node_type!r} in sub-workflow"
                raise ValueError(msg)

            params = {key: value for key, value in step.items() if key != "type"}
            node_name = str(params.get("name") or step.get("name") or node_type)
            params.setdefault("name", node_name)

            node_instance = node_class(**params)
            output = await node_instance(sub_state, config)
            node_payload = output["results"][node_name]
            sub_state["results"][node_name] = node_payload

            step_results.append({"name": node_name, "result": node_payload})
            result_lookup[node_name] = node_payload

        if self.propagate_to_parent:
            parent_results = state.setdefault("results", {})
            if isinstance(parent_results, Mapping):
                parent_results.update(sub_state["results"])
            else:
                state["results"] = sub_state["results"]

        final_step = self.result_step or step_results[-1]["name"]
        final_result = result_lookup.get(final_step)

        payload: dict[str, Any] = {
            "steps": step_results,
            "result": final_result,
        }
        if self.include_state:
            payload["state"] = _normalise_state_snapshot(sub_state)
        return payload


__all__ = [
    "PythonSandboxNode",
    "JavaScriptSandboxNode",
    "DebugNode",
    "SubWorkflowNode",
]
