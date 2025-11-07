"""Restricted Python execution node implementation."""

from __future__ import annotations
import warnings
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from RestrictedPython import compile_restricted
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


__all__ = ["PythonSandboxNode"]
