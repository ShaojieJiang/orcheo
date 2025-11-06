"""Typer application setup for workflow CLI commands."""

from __future__ import annotations
from typing import Annotated
import typer
from orcheo_sdk.cli.state import CLIState


workflow_app = typer.Typer(help="Inspect and operate on workflows.")

WorkflowIdArgument = Annotated[
    str,
    typer.Argument(help="Workflow identifier."),
]
ActorOption = Annotated[
    str,
    typer.Option("--actor", help="Actor triggering the run."),
]
InputsOption = Annotated[
    str | None,
    typer.Option("--inputs", help="JSON inputs payload."),
]
InputsFileOption = Annotated[
    str | None,
    typer.Option("--inputs-file", help="Path to JSON file with inputs."),
]
ForceOption = Annotated[
    bool,
    typer.Option("--force", help="Skip confirmation prompt."),
]
FilePathArgument = Annotated[
    str,
    typer.Argument(help="Path to workflow file (Python or JSON)."),
]
WorkflowIdOption = Annotated[
    str | None,
    typer.Option("--id", help="Workflow ID (for updates). Creates new if omitted."),
]
EntrypointOption = Annotated[
    str | None,
    typer.Option(
        "--entrypoint",
        help=(
            "Entrypoint function/variable for LangGraph scripts "
            "(auto-detect if omitted)."
        ),
    ),
]
WorkflowNameOption = Annotated[
    str | None,
    typer.Option(
        "--name",
        "-n",
        help="Rename the workflow when uploading.",
    ),
]
OutputPathOption = Annotated[
    str | None,
    typer.Option("--output", "-o", help="Output file path (default: stdout)."),
]
FormatOption = Annotated[
    str,
    typer.Option("--format", "-f", help="Output format (auto, json, or python)."),
]


def _state(ctx: typer.Context) -> CLIState:
    """Retrieve CLI state from Typer context."""
    return ctx.ensure_object(CLIState)


__all__ = [
    "workflow_app",
    "WorkflowIdArgument",
    "ActorOption",
    "InputsOption",
    "InputsFileOption",
    "ForceOption",
    "FilePathArgument",
    "WorkflowIdOption",
    "EntrypointOption",
    "WorkflowNameOption",
    "OutputPathOption",
    "FormatOption",
    "_state",
]
