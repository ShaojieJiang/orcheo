"""JavaScript sandbox node backed by py-mini-racer."""

from __future__ import annotations
import json
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


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


__all__ = ["JavaScriptSandboxNode"]
