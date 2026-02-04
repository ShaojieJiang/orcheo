"""Reference code generation commands."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Annotated
import typer
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import print_json, render_json
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.utils import load_with_cache
from orcheo_sdk.services import (
    generate_workflow_scaffold_data,
    generate_workflow_template_data,
)


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
    data = generate_workflow_scaffold_data(
        state.client,
        workflow_id,
        actor=actor,
        workflow=workflow,
        versions=versions,
    )
    if not state.human:
        print_json(data)
        return
    state.console.print(data["code"])

    render_json(state.console, data["workflow"], title="Workflow metadata")
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
    template_data = generate_workflow_template_data()
    template = template_data["code"]
    # Write the template to file
    try:
        output_path.write_text(template)
    except OSError as exc:  # pragma: no cover - filesystem error
        msg = f"Unable to write workflow template to {output_path}: {exc}".rstrip()
        raise CLIError(msg) from exc
    if not state.human:
        print_json({"status": "success", "path": str(output_path)})
        return
    state.console.print(f"[green]Created workflow template: {output_path}[/green]")
    state.console.print("\nNext steps:")
    state.console.print(
        f"  1. Edit [cyan]{output_path}[/cyan] to customize your workflow"
    )
    state.console.print(f"  2. Test locally: [cyan]python {output_path}[/cyan]")
    state.console.print(
        f"  3. Upload to Orcheo: [cyan]orcheo workflow upload {output_path}[/cyan]"
    )
