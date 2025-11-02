"""Reference code generation commands."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Annotated
import typer
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import render_json
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.utils import load_with_cache


code_app = typer.Typer(help="Generate workflow or node scaffolds.")

WorkflowIdArgument = Annotated[
    str,
    typer.Argument(help="Workflow identifier."),
]
ActorOption = Annotated[
    str,
    typer.Option("--actor", help="Actor used in the snippet."),
]


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


@code_app.command("scaffold")
def scaffold_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    actor: ActorOption = "cli",
) -> None:
    """Generate a Python snippet that triggers the workflow via the SDK."""
    state = _state(ctx)
    workflow, workflow_cached, workflow_stale = load_with_cache(
        state,
        f"workflow:{workflow_id}",
        lambda: state.client.get(f"/api/workflows/{workflow_id}"),
    )
    versions, versions_cached, versions_stale = load_with_cache(
        state,
        f"workflow:{workflow_id}:versions",
        lambda: state.client.get(f"/api/workflows/{workflow_id}/versions"),
    )
    if not versions:
        raise typer.BadParameter("Workflow has no versions to scaffold.")
    latest = max(versions, key=lambda entry: entry.get("version", 0))
    version_id = latest.get("id")
    if not version_id:
        raise typer.BadParameter("Latest workflow version is missing an id field.")

    snippet = f"""import os
from orcheo_sdk import HttpWorkflowExecutor, OrcheoClient

client = OrcheoClient(base_url=\"{state.client.base_url}\")
executor = HttpWorkflowExecutor(
    client,
    auth_token=os.environ.get(\"ORCHEO_SERVICE_TOKEN\"),
)

result = executor.trigger_run(
    \"{workflow_id}\",
    workflow_version_id=\"{version_id}\",
    triggered_by=\"{actor}\",
    inputs={{}},
)
print(result)
"""
    state.console.print(snippet)

    render_json(state.console, workflow, title="Workflow metadata")
    if workflow_cached or versions_cached:
        note = "[yellow]Using cached data[/yellow] for workflow scaffold"
        if workflow_stale or versions_stale:
            note += " (older than TTL)"
        state.console.print(note)


@code_app.command("template")
def generate_template(
    ctx: typer.Context,
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output file path (default: workflow.py)"),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Workflow name (default: my_workflow)"),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing file without confirmation"),
    ] = False,
) -> None:
    """Generate a minimal Python LangGraph workflow template.

    Creates a simple LangGraph workflow file that can be used as a starting point
    for building custom workflows with Orcheo.
    """
    state = _state(ctx)
    output_path = Path(output or "workflow.py")

    # Check if file exists and handle overwrite
    if output_path.exists():
        if output_path.is_dir():
            raise CLIError(f"{output_path} is a directory; provide a file path")
        if not overwrite:
            state.console.print(
                f"[yellow]File {output_path} already exists. "
                "Use --force to overwrite.[/yellow]"
            )
            raise typer.Exit(code=1)

    parent = output_path.parent
    if parent.exists() and not parent.is_dir():
        raise CLIError(f"Parent path {parent} is not a directory")

    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - filesystem error
            msg = f"Unable to create parent directory for {output_path}: {exc}".rstrip()
            raise CLIError(msg) from exc

    directory = parent if str(parent) else Path.cwd()
    if not os.access(directory, os.W_OK):  # pragma: no cover - permission
        raise CLIError(f"No write permission in directory {directory}")

    # Generate the template content
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

    # Write the template to file
    try:
        output_path.write_text(template)
    except OSError as exc:  # pragma: no cover - filesystem error
        msg = f"Unable to write workflow template to {output_path}: {exc}".rstrip()
        raise CLIError(msg) from exc
    state.console.print(f"[green]Created workflow template: {output_path}[/green]")
    state.console.print("\nNext steps:")
    state.console.print(
        f"  1. Edit [cyan]{output_path}[/cyan] to customize your workflow"
    )
    state.console.print(f"  2. Test locally: [cyan]python {output_path}[/cyan]")
    state.console.print(
        f"  3. Upload to Orcheo: [cyan]orcheo workflow upload {output_path}[/cyan]"
    )
