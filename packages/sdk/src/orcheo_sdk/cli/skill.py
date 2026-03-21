"""Agent Skills lifecycle CLI commands."""

from __future__ import annotations
from typing import Annotated
import typer
from orcheo.skills.manager import SkillError
from orcheo_sdk.cli.output import (
    print_json,
    print_markdown_table,
    render_json,
    render_table,
)
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.services import (
    install_skill_data,
    list_skills_data,
    show_skill_data,
    uninstall_skill_data,
    validate_skill_data,
)


skill_app = typer.Typer(help="Install, inspect, and manage Agent Skills.")

NameArgument = Annotated[
    str,
    typer.Argument(help="Skill name."),
]
RefArgument = Annotated[
    str,
    typer.Argument(help="Local directory path containing a SKILL.md file."),
]


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


@skill_app.command("list")
def list_skills(ctx: typer.Context) -> None:
    """List installed agent skills and their status."""
    state = _state(ctx)
    rows = list_skills_data()
    if not state.human:
        print_markdown_table(rows)
        return
    render_table(
        state.console,
        title="Installed Skills",
        columns=["Name", "Description", "Source", "Status"],
        rows=[
            [
                row["name"],
                row["description"],
                row["source"],
                row["status"],
            ]
            for row in rows
        ],
        column_overflow={"Description": "fold", "Source": "fold"},
    )


@skill_app.command("show")
def show_skill(
    ctx: typer.Context,
    name: NameArgument,
) -> None:
    """Show agent skill details."""
    state = _state(ctx)
    try:
        payload = show_skill_data(name)
    except SkillError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not state.human:
        print_json(payload)
        return
    render_json(state.console, payload, title=name)


@skill_app.command("install")
def install_skill(
    ctx: typer.Context,
    ref: RefArgument,
) -> None:
    """Install an agent skill from a local directory."""
    state = _state(ctx)
    try:
        payload = install_skill_data(ref)
    except SkillError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not state.human:
        print_json(payload)
        return
    render_json(state.console, payload, title="Installed Skill")


@skill_app.command("uninstall")
def uninstall_skill(
    ctx: typer.Context,
    name: NameArgument,
) -> None:
    """Uninstall an agent skill."""
    state = _state(ctx)
    try:
        payload = uninstall_skill_data(name)
    except SkillError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not state.human:
        print_json(payload)
        return
    state.console.print(f"Uninstalled skill {name}")


@skill_app.command("validate")
def validate_skill(
    ctx: typer.Context,
    ref: RefArgument,
) -> None:
    """Validate a skill directory without installing."""
    state = _state(ctx)
    try:
        result = validate_skill_data(ref)
    except SkillError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if result.valid:
        payload = {
            "valid": True,
            "name": result.skill_metadata.name if result.skill_metadata else "",
        }
        if not state.human:
            print_json(payload)
            return
        state.console.print(f"Skill is valid: {payload['name']}")
    else:
        errors = [{"field": err.field, "message": err.message} for err in result.errors]
        payload_err = {"valid": False, "errors": errors}
        if not state.human:
            print_json(payload_err)
            raise typer.Exit(code=1)
        for err in result.errors:
            state.console.print(f"  {err.field}: {err.message}")
        raise typer.Exit(code=1)


__all__ = ["skill_app"]
