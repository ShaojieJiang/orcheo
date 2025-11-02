"""Code generation service operations.

Pure business logic for code generation, shared by CLI and MCP interfaces.
"""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.http import ApiClient


def generate_workflow_scaffold_data(
    client: ApiClient,
    workflow_id: str,
    actor: str = "api",
    workflow: dict[str, Any] | None = None,
    versions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate workflow trigger code.

    Args:
        client: API client instance
        workflow_id: Workflow identifier
        actor: Actor used in generated code
        workflow: Optional pre-fetched workflow metadata
        versions: Optional pre-fetched workflow versions

    Returns:
        Dictionary with code, workflow metadata, and versions

    Raises:
        CLIError: If workflow has no versions
    """
    if workflow is None:
        workflow = client.get(f"/api/workflows/{workflow_id}")
    if versions is None:
        versions = client.get(f"/api/workflows/{workflow_id}/versions")

    if not versions:
        raise CLIError("Workflow has no versions to scaffold.")

    latest = max(versions, key=lambda entry: entry.get("version", 0))
    version_id = latest.get("id")

    if not version_id:
        raise CLIError("Latest workflow version is missing an id field.")

    snippet = f"""import os
from orcheo_sdk import HttpWorkflowExecutor, OrcheoClient

client = OrcheoClient(base_url="{client.base_url}")
executor = HttpWorkflowExecutor(
    client,
    auth_token=os.environ.get("ORCHEO_SERVICE_TOKEN"),
)

result = executor.trigger_run(
    "{workflow_id}",
    workflow_version_id="{version_id}",
    triggered_by="{actor}",
    inputs={{}},
)
print(result)
"""

    return {
        "code": snippet,
        "workflow": workflow,
        "versions": versions,
    }


def generate_workflow_template_data() -> dict[str, str]:
    """Generate minimal workflow template.

    Returns:
        Dictionary with template code and description
    """
    template = '''"""Minimal LangGraph workflow for Orcheo.

This is a simple LangGraph workflow template demonstrating state access in Orcheo.
You can customize the state definition, add more nodes, and define complex logic.

Key features:
- Use plain dict for state (StateGraph(dict))
- Access inputs directly: state.get("param_name")
- Define any custom state fields you need
- No predefined "messages" or "results" fields
- RestrictedPython limitations apply (no variables starting with "_")
"""

from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.logic import SetVariableNode


def build_graph():
    """Build and return the LangGraph workflow."""
    graph = StateGraph(State)
    graph.add_node(
        "set_variable",
        SetVariableNode(
            name="set_variable",
            variables={
                "output": "Hi there!",
            },
        ),
    )
    graph.add_edge(START, "set_variable")
    graph.add_edge("set_variable", END)
    return graph


if __name__ == "__main__":
    # Test the workflow locally
    import asyncio

    graph = build_graph().compile()
    result = asyncio.run(graph.ainvoke({}))
    print(result)
    print(result["results"]["set_variable"]["output"])
'''

    return {
        "code": template,
        "description": "Minimal LangGraph workflow template for Orcheo",
    }
