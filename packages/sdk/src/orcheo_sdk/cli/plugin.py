"""Plugin lifecycle CLI commands."""

from __future__ import annotations
import json
import os
import shutil
import subprocess
from pathlib import Path
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
RuntimeOption = Annotated[
    str,
    typer.Option(
        "--runtime",
        help="Plugin runtime target: auto, local, or stack.",
    ),
]

_STACK_RUNTIME_SERVICES = ("backend", "worker", "celery-beat")


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


def _resolve_stack_project_dir() -> Path:
    configured = os.getenv("ORCHEO_STACK_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".orcheo" / "stack"


def _stack_compose_base_args() -> list[str]:
    stack_dir = _resolve_stack_project_dir()
    compose_file = stack_dir / "docker-compose.yml"
    if not compose_file.exists():
        raise typer.BadParameter(
            "Stack docker-compose file not found. Run 'orcheo install --yes' first."
        )
    return [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "--project-directory",
        str(stack_dir),
    ]


def _normalize_runtime(runtime: str) -> str:
    resolved = runtime.strip().lower()
    if resolved not in {"auto", "local", "stack"}:
        raise typer.BadParameter("Runtime must be one of: auto, local, stack.")
    return resolved


def _use_stack_runtime(runtime: str) -> bool:
    resolved = _normalize_runtime(runtime)
    if resolved == "local":
        return False
    if resolved == "stack":
        return True
    stack_dir = _resolve_stack_project_dir()
    return (stack_dir / "docker-compose.yml").exists()


def _run_stack_subprocess(
    command: list[str],
    *,
    expected_exit_codes: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    if shutil.which("docker") is None:
        raise typer.BadParameter(
            "Docker is not installed or not in PATH. Install Docker and retry."
        )
    if expected_exit_codes is None:  # pragma: no branch
        expected_exit_codes = {0}
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in expected_exit_codes:
        message = result.stderr.strip() or result.stdout.strip() or "Command failed."
        raise typer.BadParameter(message)
    return result


def _running_stack_services() -> set[str]:
    compose_base_args = _stack_compose_base_args()
    result = _run_stack_subprocess(
        [*compose_base_args, "ps", "--services", "--status", "running"]
    )
    return {
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() in _STACK_RUNTIME_SERVICES
    }


def _stack_plugin_command(
    *,
    args: list[str],
    human: bool,
) -> list[str]:
    compose_base_args = _stack_compose_base_args()
    running = _running_stack_services()
    runtime_args = [*args, "--runtime", "local"]
    if "backend" in running:
        return [
            *compose_base_args,
            "exec",
            "-T",
            "backend",
            "orcheo",
            *(["--human"] if human else []),
            "plugin",
            *runtime_args,
        ]
    return [
        *compose_base_args,
        "run",
        "--rm",
        "-T",
        "--no-deps",
        "backend",
        "orcheo",
        *(["--human"] if human else []),
        "plugin",
        *runtime_args,
    ]


def _run_stack_plugin_passthrough(*, args: list[str], state: CLIState) -> None:
    expected_exit_codes = {0, 1} if args and args[0] == "doctor" else {0}
    result = _run_stack_subprocess(
        _stack_plugin_command(args=args, human=state.human),
        expected_exit_codes=expected_exit_codes,
    )
    output = result.stdout.rstrip()
    if output:
        if state.human:
            state.console.print(output)
        else:
            typer.echo(output)
    if args and args[0] == "doctor" and result.returncode == 1:
        raise typer.Exit(code=1)


def _is_local_plugin_ref(ref: str) -> bool:
    candidate = Path(ref).expanduser()
    if candidate.exists():
        return True
    if ref.startswith(("./", "../", "~/")):
        return True
    if candidate.suffix == ".whl":
        return True
    return "/" in ref or "\\" in ref


def _run_stack_plugin_json(args: list[str]) -> Any:
    result = _run_stack_subprocess(
        _stack_plugin_command(args=args, human=False),
    )
    payload = result.stdout.strip()
    if not payload:
        return None
    return json.loads(payload)


def _restart_running_stack_services(console_state: CLIState) -> None:
    running = _running_stack_services()
    if not running:
        return
    compose_base_args = _stack_compose_base_args()
    _run_stack_subprocess([*compose_base_args, "restart", *sorted(running)])
    if console_state.human:
        console_state.console.print(
            "Restarted stack services: " + ", ".join(sorted(running))
        )


def _payload_requires_restart(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    impact = payload.get("impact")
    return isinstance(impact, dict) and bool(impact.get("restart_required"))


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
    if console_state.human:  # pragma: no branch
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
def list_plugins(
    ctx: typer.Context,
    runtime: RuntimeOption = "auto",
) -> None:
    """List installed plugins and their status."""
    state = _state(ctx)
    if _use_stack_runtime(runtime):
        _run_stack_plugin_passthrough(args=["list"], state=state)
        return
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
def show_plugin(
    ctx: typer.Context,
    name: NameArgument,
    runtime: RuntimeOption = "auto",
) -> None:
    """Show plugin details."""
    state = _state(ctx)
    if _use_stack_runtime(runtime):
        _run_stack_plugin_passthrough(args=["show", name], state=state)
        return
    try:
        payload = show_plugin_data(name)
    except PluginError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not state.human:
        print_json(payload)
        return
    render_json(state.console, payload, title=name)


@plugin_app.command("install")
def install_plugin(
    ctx: typer.Context,
    ref: RefArgument,
    runtime: RuntimeOption = "auto",
) -> None:
    """Install a plugin from a package, path, wheel, or git ref."""
    state = _state(ctx)
    use_stack_runtime = _use_stack_runtime(runtime) and not _is_local_plugin_ref(ref)
    if use_stack_runtime:
        payload = _run_stack_plugin_json(["install", ref])
        if _payload_requires_restart(payload):  # pragma: no branch
            _restart_running_stack_services(state)
        if not state.human:
            print_json(payload)
            return
        render_json(state.console, payload["plugin"], title="Installed Plugin")
        _render_impact(
            state,
            PluginImpactSummary(**payload["impact"]),
        )
        return
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
def doctor_plugins(
    ctx: typer.Context,
    runtime: RuntimeOption = "auto",
) -> None:
    """Inspect plugin state and report errors and warnings."""
    state = _state(ctx)
    if _use_stack_runtime(runtime):
        _run_stack_plugin_passthrough(args=["doctor"], state=state)
        return
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
