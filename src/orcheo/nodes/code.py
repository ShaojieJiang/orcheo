"""Code execution node for Orcheo."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="PythonCode",
        description="Execute Python code",
        category="code",
    )
)
class PythonCode(TaskNode):
    """Node for executing Python code."""

    code: str

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
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
