"""Plugin lifecycle CLI commands."""

from __future__ import annotations
from typing import Annotated, Any
import typer
from orcheo.plugins import PluginImpactSummary
from orcheo.plugins.manager import PluginError
from orcheo_sdk.cli.output import (
    print_json,
    print_markdown_table,
    render_json,
    render_table,
)
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.services import (
    disable_plugin_data,
    doctor_plugins_data,
    enable_plugin_data,
    install_plugin_data,
    list_plugins_data,
    preview_disable_plugin_data,
    preview_enable_plugin_data,
    preview_uninstall_plugin_data,
    preview_update_all_plugins_data,
    preview_update_plugin_data,
    show_plugin_data,
    uninstall_plugin_data,
    update_all_plugins_data,
    update_plugin_data,
)


plugin_app = typer.Typer(help="Install, inspect, and manage Orcheo plugins.")

NameArgument = Annotated[
    str,
    typer.Argument(help="Plugin package name."),
]
RefArgument = Annotated[
    str,
    typer.Argument(help="Package, path, wheel, or git reference."),
]


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


def _impact_to_dict(impact: PluginImpactSummary) -> dict[str, Any]:
    return {
        "change_type": impact.change_type,
        "affected_component_kinds": impact.affected_component_kinds,
        "affected_component_ids": impact.affected_component_ids,
        "activation_mode": impact.activation_mode,
        "prompt_required": impact.prompt_required,
        "restart_required": impact.restart_required,
    }


def _render_impact(console_state: CLIState, impact: PluginImpactSummary) -> None:
    if console_state.human:
        render_json(console_state.console, _impact_to_dict(impact), title="Impact")


def _maybe_confirm(
    *,
    impact: PluginImpactSummary,
    prompt_text: str,
    state: CLIState,
    force: bool,
) -> None:
    if force or not impact.prompt_required:
        return
    if not state.human:
        raise typer.BadParameter(
            "This operation requires confirmation. Re-run with --force or --human."
        )
    should_continue = typer.confirm(prompt_text, default=False)
    if not should_continue:
        raise typer.Exit(code=1)


@plugin_app.command("list")
def list_plugins(ctx: typer.Context) -> None:
    """List installed plugins and their status."""
    state = _state(ctx)
    rows = list_plugins_data()
    if not state.human:
        print_markdown_table(rows)
        return
    render_table(
        state.console,
        title="Installed Plugins",
        columns=["Name", "Enabled", "Status", "Version", "Exports", "Source"],
        rows=[
            [
                row["name"],
                row["enabled"],
                row["status"],
                row["version"],
                ", ".join(row["exports"]),
                row["source"],
            ]
            for row in rows
        ],
        column_overflow={"Source": "fold"},
    )


@plugin_app.command("show")
def show_plugin(ctx: typer.Context, name: NameArgument) -> None:
    """Show plugin details."""
    state = _state(ctx)
    try:
        payload = show_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not state.human:
        print_json(payload)
        return
    render_json(state.console, payload, title=name)


@plugin_app.command("install")
def install_plugin(ctx: typer.Context, ref: RefArgument) -> None:
    """Install a plugin from a package, path, wheel, or git ref."""
    state = _state(ctx)
    try:
        payload = install_plugin_data(ref)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not state.human:
        print_json(
            {
                "plugin": payload["plugin"],
                "impact": _impact_to_dict(payload["impact"]),
            }
        )
        return
    render_json(state.console, payload["plugin"], title="Installed Plugin")
    _render_impact(state, payload["impact"])


@plugin_app.command("update")
def update_plugin(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(help="Plugin package name."),
    ] = None,
    all_plugins: Annotated[
        bool,
        typer.Option("--all", help="Update all installed plugins."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompts."),
    ] = False,
) -> None:
    """Update a plugin using the stored install reference."""
    state = _state(ctx)
    if all_plugins:
        try:
            preview_all = preview_update_all_plugins_data()
        except PluginError as exc:
            raise typer.BadParameter(str(exc)) from exc
        for item in preview_all:
            _maybe_confirm(
                impact=item["impact"],
                prompt_text=(
                    f"Apply update for {item['name']} with activation mode "
                    f"{item['impact'].activation_mode}?"
                ),
                state=state,
                force=force,
            )
        try:
            payload_all = update_all_plugins_data()
        except PluginError as exc:
            raise typer.BadParameter(str(exc)) from exc
        if not state.human:
            print_json(
                [
                    {
                        "plugin": item["plugin"],
                        "impact": _impact_to_dict(item["impact"]),
                    }
                    for item in payload_all
                ]
            )
            return
        render_json(
            state.console,
            [
                {
                    "plugin": item["plugin"],
                    "impact": _impact_to_dict(item["impact"]),
                }
                for item in payload_all
            ],
            title="Updated Plugins",
        )
        return

    if not name:
        raise typer.BadParameter("Provide a plugin name or pass --all.")
    try:
        preview_single = preview_update_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _maybe_confirm(
        impact=preview_single["impact"],
        prompt_text=(
            "Update "
            f"{name} with activation mode "
            f"{preview_single['impact'].activation_mode}?"
        ),
        state=state,
        force=force,
    )
    try:
        payload_single = update_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not state.human:
        print_json(
            {
                "plugin": payload_single["plugin"],
                "impact": _impact_to_dict(payload_single["impact"]),
            }
        )
        return
    render_json(state.console, payload_single["plugin"], title="Updated Plugin")
    _render_impact(state, payload_single["impact"])


@plugin_app.command("uninstall")
def uninstall_plugin(
    ctx: typer.Context,
    name: NameArgument,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompts."),
    ] = False,
) -> None:
    """Uninstall a plugin and rebuild the shared plugin environment."""
    state = _state(ctx)
    try:
        payload = preview_uninstall_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    impact = payload["impact"]
    _maybe_confirm(
        impact=impact,
        prompt_text=(f"Uninstall {name}? Activation mode: {impact.activation_mode}."),
        state=state,
        force=force,
    )
    try:
        payload = uninstall_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    impact = payload["impact"]
    if not state.human:
        print_json({"name": name, "impact": _impact_to_dict(impact)})
        return
    state.console.print(f"Uninstalled plugin {name}")
    _render_impact(state, impact)


@plugin_app.command("enable")
def enable_plugin(
    ctx: typer.Context,
    name: NameArgument,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompts."),
    ] = False,
) -> None:
    """Enable a previously installed plugin."""
    state = _state(ctx)
    try:
        payload = preview_enable_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    impact = payload["impact"]
    _maybe_confirm(
        impact=impact,
        prompt_text=f"Enable {name}? Activation mode: {impact.activation_mode}.",
        state=state,
        force=force,
    )
    try:
        payload = enable_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    impact = payload["impact"]
    if not state.human:
        print_json({"name": name, "impact": _impact_to_dict(impact)})
        return
    state.console.print(f"Enabled plugin {name}")
    _render_impact(state, impact)


@plugin_app.command("disable")
def disable_plugin(
    ctx: typer.Context,
    name: NameArgument,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompts."),
    ] = False,
) -> None:
    """Disable a plugin without removing its desired source reference."""
    state = _state(ctx)
    try:
        payload = preview_disable_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    impact = payload["impact"]
    _maybe_confirm(
        impact=impact,
        prompt_text=f"Disable {name}? Activation mode: {impact.activation_mode}.",
        state=state,
        force=force,
    )
    try:
        payload = disable_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    impact = payload["impact"]
    if not state.human:
        print_json({"name": name, "impact": _impact_to_dict(impact)})
        return
    state.console.print(f"Disabled plugin {name}")
    _render_impact(state, impact)


@plugin_app.command("doctor")
def doctor_plugins(ctx: typer.Context) -> None:
    """Inspect plugin state and report errors and warnings."""
    state = _state(ctx)
    payload = doctor_plugins_data()
    if not state.human:
        print_json(payload)
        if payload["has_errors"]:
            raise typer.Exit(code=1)
        return
    render_table(
        state.console,
        title="Plugin Doctor",
        columns=["Check", "Severity", "OK", "Message"],
        rows=[
            [check["name"], check["severity"], check["ok"], check["message"]]
            for check in payload["checks"]
        ],
        column_overflow={"Message": "fold"},
    )
    if payload["has_errors"]:
        raise typer.Exit(code=1)


__all__ = ["plugin_app"]
