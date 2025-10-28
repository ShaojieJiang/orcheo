"""Reference code generation commands."""

from __future__ import annotations
from textwrap import dedent
import typer
from .api import ApiRequestError
from .utils import abort_with_error, get_context


code_app = typer.Typer(help="Generate Orcheo SDK reference code.", add_completion=True)


@code_app.command("scaffold")
def scaffold_workflow(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="Workflow identifier."),
) -> None:
    """Generate a Python snippet that triggers a workflow."""
    context = get_context(ctx)

    try:
        versions = context.client.get_json(
            f"/workflows/{workflow_id}/versions",
            offline=context.offline,
            description="workflow versions",
        )
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    entries = versions.data if isinstance(versions.data, list) else []
    if not entries:
        context.console.print(
            "[red]Workflow has no versions; deploy a version before scaffolding.[/red]"
        )
        raise typer.Exit(code=1)

    latest = max(
        (entry for entry in entries if isinstance(entry, dict)),
        key=lambda item: int(item.get("version", 0) or 0),
    )
    version_id = str(latest.get("id"))

    api_root = context.settings.api_url.rstrip("/")
    if api_root.endswith("/api"):
        api_root = api_root[: -len("/api")]

    snippet = dedent(
        f"""
        import os
        from orcheo_sdk import HttpWorkflowExecutor, OrcheoClient

        api_url = os.getenv("ORCHEO_API_URL", "{api_root}")
        service_token = os.getenv("ORCHEO_SERVICE_TOKEN")

        default_headers = {{}}
        if service_token:
            default_headers["Authorization"] = f"Bearer {{service_token}}"

        client = OrcheoClient(base_url=api_url, default_headers=default_headers)
        executor = HttpWorkflowExecutor(client, auth_token=service_token)

        run = executor.trigger_run(
            workflow_id="{workflow_id}",
            workflow_version_id="{version_id}",
            triggered_by="cli",
            inputs={{}},
        )

        print(run)
        """
    ).strip()

    context.console.print("[bold]Python scaffold:[/bold]")
    context.console.print(snippet)


__all__ = ["code_app"]
