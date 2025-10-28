"""Workflow management commands."""

from __future__ import annotations
import json
import re
from typing import Any
import typer
from orcheo_sdk.cli import render as renderers
from orcheo_sdk.cli.runtime import CliError, CliRuntime, render_error
from orcheo_sdk.cli.services import (
    WorkflowRunInfo,
    WorkflowVersionInfo,
    fetch_workflow_detail,
    fetch_workflow_runs,
    fetch_workflows,
    trigger_workflow_run,
)


workflow_app = typer.Typer(help="Inspect and run workflows")


def _runtime(ctx: typer.Context) -> CliRuntime:
    runtime = ctx.obj
    if not isinstance(runtime, CliRuntime):  # pragma: no cover
        raise typer.Exit(code=1)
    return runtime


def _select_version(
    versions: list[WorkflowVersionInfo],
    requested: int | None,
) -> WorkflowVersionInfo:
    if not versions:
        raise CliError("Workflow has no versions to select from")
    if requested is None:
        return max(versions, key=lambda version: version.version)
    for version in versions:
        if version.version == requested:
            return version
    raise CliError(f"Workflow version {requested} was not found")


def _normalise_identifier(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_]", "_", value)
    return slug or "node"


def _label_for_node(node: dict[str, Any]) -> str:
    node_type = str(node.get("type", "")) or "node"
    node_name = str(node.get("name", ""))
    label = node_type
    if node_name and node_name != node_type:
        label = f"{node_type}: {node_name}"
    return label.replace('"', '"')


def build_mermaid(graph: dict[str, Any]) -> str:
    """Return a Mermaid diagram representing the supplied graph."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    conditionals = graph.get("conditional_edges", [])

    lines: list[str] = ["flowchart TD"]
    declared: set[str] = set()

    for node in nodes:
        name = str(node.get("name", "")) or "node"
        identifier = _normalise_identifier(name)
        declared.add(identifier)
        label = _label_for_node(node)
        lines.append(f'    {identifier}["{label}"]')

    for source, target in edges:
        src_id = _normalise_identifier(str(source))
        tgt_id = _normalise_identifier(str(target))
        lines.append(f"    {src_id} --> {tgt_id}")

    for branch in conditionals:
        source = branch.get("source")
        if not source:
            continue
        src_id = _normalise_identifier(str(source))
        mapping = branch.get("mapping", {})
        for key, target in mapping.items():
            tgt_id = _normalise_identifier(str(target))
            label = str(key).replace('"', '"')
            lines.append(f'    {src_id} -- "{label}" --> {tgt_id}')
        default = branch.get("default")
        if default:
            tgt_id = _normalise_identifier(str(default))
            lines.append(f'    {src_id} -- "default" --> {tgt_id}')

    if len(lines) == 1:
        lines.append("    %% No nodes defined in workflow")
    return "\n".join(lines)


@workflow_app.command("list", help="List workflows in the connected workspace")
def list_workflows(ctx: typer.Context) -> None:
    """Render a table of workflows available via the API."""
    runtime = _runtime(ctx)
    if runtime.offline:
        render_error(runtime.console, "Workflow listing requires network access")
        raise typer.Exit(code=1)
    try:
        workflows = fetch_workflows(runtime)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc
    renderers.render_workflow_table(runtime.console, workflows)


@workflow_app.command("show", help="Show workflow metadata and latest runs")
def show_workflow(
    ctx: typer.Context,
    workflow_id: str,
    version: int | None = typer.Option(
        None,
        "--version",
        help="Select a specific workflow version",
    ),
) -> None:
    """Display workflow metadata, latest runs, and a Mermaid representation."""
    runtime = _runtime(ctx)
    try:
        detail, versions, cache_entry = fetch_workflow_detail(runtime, workflow_id)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    try:
        selected_version = _select_version(versions, version)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    mermaid = build_mermaid(selected_version.graph)
    runs: list[WorkflowRunInfo]
    try:
        runs = fetch_workflow_runs(runtime, workflow_id)
    except CliError:
        runs = []

    cache_warning: str | None = None
    if cache_entry and runtime.cache.is_stale(cache_entry):
        cache_warning = (
            "Workflow data is older than 24 hours; refresh online to update."
        )

    renderers.render_workflow_detail(
        runtime.console,
        detail,
        latest_version=selected_version,
        runs=runs,
        mermaid=mermaid,
        cache_warning=cache_warning,
    )


@workflow_app.command("run", help="Trigger a workflow execution")
def run_workflow(
    ctx: typer.Context,
    workflow_id: str,
    version: int | None = typer.Option(
        None,
        "--version",
        help="Workflow version to execute",
    ),
    actor: str = typer.Option("cli", "--actor", help="Actor recorded for the run"),
    inputs: str | None = typer.Option(
        None,
        "--inputs",
        help="JSON payload to pass as workflow inputs",
    ),
) -> None:
    """Trigger a workflow run using the latest or requested version."""
    runtime = _runtime(ctx)
    if runtime.offline:
        render_error(runtime.console, "Running workflows is unavailable offline")
        raise typer.Exit(code=1)

    try:
        detail, versions, _cache_entry = fetch_workflow_detail(runtime, workflow_id)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    try:
        selected_version = _select_version(versions, version)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    payload: dict[str, Any] | None = None
    if inputs:
        try:
            candidate = json.loads(inputs)
        except json.JSONDecodeError as exc:
            render_error(runtime.console, f"Invalid JSON for --inputs: {exc}")
            raise typer.Exit(code=1) from exc
        if not isinstance(candidate, dict):
            render_error(runtime.console, "Workflow inputs must be a JSON object")
            raise typer.Exit(code=1)
        payload = candidate

    try:
        run = trigger_workflow_run(
            runtime,
            workflow_id=workflow_id,
            workflow_version_id=selected_version.id,
            actor=actor,
            inputs=payload,
        )
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    runtime.console.print(
        "Dispatched workflow run "
        f"for '{detail.name}' (version {selected_version.version})"
    )
    runtime.console.print(f"Run ID: {run.id}")
    runtime.console.print(f"Status: {run.status}")
