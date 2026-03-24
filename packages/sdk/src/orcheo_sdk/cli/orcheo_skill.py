"""Standalone CLI for installing the official Orcheo skill."""

from __future__ import annotations
from typing import Annotated
import typer
from rich.console import Console
from orcheo.skills.manager import SkillError
from orcheo_sdk.cli.output import print_json, render_json, render_table
from orcheo_sdk.services.orcheo_skill import (
    install_orcheo_skill_data,
    uninstall_orcheo_skill_data,
    update_orcheo_skill_data,
)


orcheo_skill_app = typer.Typer(
    help="Install, uninstall, or update the official Orcheo skill for Claude and Codex."
)

TargetOption = Annotated[
    list[str] | None,
    typer.Option(
        "--target",
        "-t",
        help="Install target: claude, codex, or all. Repeat for multiple targets.",
    ),
]
SourceOption = Annotated[
    str | None,
    typer.Option(
        "--source",
        help=(
            "Local skill directory to install instead of downloading from the "
            "official repository."
        ),
    ),
]


def _render_result(payload: dict[str, object], *, human: bool) -> None:
    if not human:
        print_json(payload)
        return

    console = Console()
    render_json(console, {"skill": payload["skill"], "action": payload["action"]})
    targets = payload.get("targets", [])
    if isinstance(targets, list):
        render_table(
            console,
            title="Targets",
            columns=["Target", "Status", "Path", "Source"],
            rows=[
                [
                    target.get("target", ""),
                    target.get("status", ""),
                    target.get("path", ""),
                    target.get("source", ""),
                ]
                for target in targets
                if isinstance(target, dict)
            ],
            column_overflow={"Path": "fold", "Source": "fold"},
        )


@orcheo_skill_app.command("install")
def install_orcheo_skill(
    target: TargetOption = None,
    source: SourceOption = None,
    human: Annotated[
        bool,
        typer.Option("--human", help="Render human-friendly Rich output."),
    ] = False,
) -> None:
    """Install the official Orcheo skill."""
    try:
        payload = install_orcheo_skill_data(targets=target, source=source)
    except SkillError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _render_result(payload, human=human)


@orcheo_skill_app.command("update")
def update_orcheo_skill(
    target: TargetOption = None,
    source: SourceOption = None,
    human: Annotated[
        bool,
        typer.Option("--human", help="Render human-friendly Rich output."),
    ] = False,
) -> None:
    """Update the official Orcheo skill."""
    try:
        payload = update_orcheo_skill_data(targets=target, source=source)
    except SkillError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _render_result(payload, human=human)


@orcheo_skill_app.command("uninstall")
def uninstall_orcheo_skill(
    target: TargetOption = None,
    human: Annotated[
        bool,
        typer.Option("--human", help="Render human-friendly Rich output."),
    ] = False,
) -> None:
    """Uninstall the official Orcheo skill."""
    try:
        payload = uninstall_orcheo_skill_data(targets=target)
    except SkillError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _render_result(payload, human=human)


def run() -> None:
    """Run the standalone ``orcheo-skill`` CLI."""
    orcheo_skill_app()


__all__ = ["orcheo_skill_app", "run"]
