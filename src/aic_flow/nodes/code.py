"""Code execution node for AIC Flow."""

from dataclasses import dataclass
from typing import Any
from aic_flow.graph.state import State
from aic_flow.nodes.base import TaskNode
from aic_flow.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="PythonCode",
        description="Execute Python code",
        category="code",
    )
)
@dataclass
class PythonCode(TaskNode):
    """Node for executing Python code."""

    code: str

    def run(self, state: State) -> dict[str, Any]:
        """Execute the code and return results."""
        # Ensure the code contains a return statement
        if "return" not in self.code or "return None" in self.code:
            raise ValueError("Code must contain a return statement")

        local_vars = state.copy()
        indented_code = "\n".join(
            "    " + line for line in self.code.strip().split("\n")
        )
        wrapper = f"""
def _execute():
{indented_code}
"""
        exec(wrapper, {"state": state}, local_vars)
        result = local_vars["_execute"]()  # type: ignore[typeddict-item]
        return result
