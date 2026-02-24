"""Tests for ``orcheo stack`` shortcuts."""

from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any
import pytest
import typer
from rich.console import Console
from orcheo_sdk.cli.main import (
    _resolve_stack_project_dir,
    _run_stack_command,
    app,
)


def _stack_env(base_env: dict[str, str], stack_dir: Path) -> dict[str, str]:
    env = dict(base_env)
    env["ORCHEO_STACK_DIR"] = str(stack_dir)
    return env


def test_stack_logs_shortcut_runs_compose_logs_follow(
    runner: Any,
    env: dict[str, str],
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    compose_file = stack_dir / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")

    executed: list[str] = []

    def _run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        del check
        executed[:] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("orcheo_sdk.cli.main.subprocess.run", _run)
    monkeypatch.setattr("orcheo_sdk.cli.main.shutil.which", lambda _: "/usr/bin/docker")

    result = runner.invoke(
        app,
        ["--no-update-check", "stack", "--logs"],
        env=_stack_env(env, stack_dir),
    )

    assert result.exit_code == 0
    assert executed == [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "--project-directory",
        str(stack_dir),
        "logs",
        "-f",
    ]


def test_stack_start_shortcut_runs_compose_up_detached(
    runner: Any,
    env: dict[str, str],
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    compose_file = stack_dir / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")

    executed: list[str] = []

    def _run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        del check
        executed[:] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("orcheo_sdk.cli.main.subprocess.run", _run)
    monkeypatch.setattr("orcheo_sdk.cli.main.shutil.which", lambda _: "/usr/bin/docker")

    result = runner.invoke(
        app,
        ["--no-update-check", "stack", "--start"],
        env=_stack_env(env, stack_dir),
    )

    assert result.exit_code == 0
    assert executed == [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "--project-directory",
        str(stack_dir),
        "up",
        "-d",
    ]


def test_stack_logs_treats_sigint_exit_as_success(
    runner: Any,
    env: dict[str, str],
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    compose_file = stack_dir / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")

    executed: list[str] = []

    def _run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        del check
        executed[:] = command
        return subprocess.CompletedProcess(command, 130)

    monkeypatch.setattr("orcheo_sdk.cli.main.subprocess.run", _run)
    monkeypatch.setattr("orcheo_sdk.cli.main.shutil.which", lambda _: "/usr/bin/docker")

    result = runner.invoke(
        app,
        ["--no-update-check", "stack", "--logs"],
        env=_stack_env(env, stack_dir),
    )

    assert result.exit_code == 0
    assert executed == [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "--project-directory",
        str(stack_dir),
        "logs",
        "-f",
    ]


def test_stack_rejects_multiple_actions(
    runner: Any,
    env: dict[str, str],
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    (stack_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr("orcheo_sdk.cli.main.shutil.which", lambda _: "/usr/bin/docker")
    called = {"value": False}
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.subprocess.run",
        lambda *args, **kwargs: (
            called.__setitem__("value", True),
            subprocess.CompletedProcess(args, 0),
        )[1],
    )

    result = runner.invoke(
        app,
        ["--no-update-check", "stack", "--logs", "--ps"],
        env=_stack_env(env, stack_dir),
    )

    assert result.exit_code == 2
    assert called["value"] is False


def test_stack_requires_existing_compose_file(
    runner: Any,
    env: dict[str, str],
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    monkeypatch.setattr("orcheo_sdk.cli.main.shutil.which", lambda _: "/usr/bin/docker")
    called = {"value": False}
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.subprocess.run",
        lambda *args, **kwargs: (
            called.__setitem__("value", True),
            subprocess.CompletedProcess(args, 0),
        )[1],
    )

    result = runner.invoke(
        app,
        ["--no-update-check", "stack", "--ps"],
        env=_stack_env(env, stack_dir),
    )

    assert result.exit_code == 2
    assert called["value"] is False


def test_stack_requires_docker_binary(
    runner: Any,
    env: dict[str, str],
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    (stack_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr("orcheo_sdk.cli.main.shutil.which", lambda _: None)
    called = {"value": False}
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.subprocess.run",
        lambda *args, **kwargs: (
            called.__setitem__("value", True),
            subprocess.CompletedProcess(args, 0),
        )[1],
    )

    result = runner.invoke(
        app,
        ["--no-update-check", "stack", "--ps"],
        env=_stack_env(env, stack_dir),
    )

    assert result.exit_code == 2
    assert called["value"] is False


# ------------------------------------------------------------------
# Coverage for previously-uncovered lines
# ------------------------------------------------------------------


def test_resolve_stack_project_dir_defaults_to_home(
    monkeypatch: Any,
) -> None:
    """When ORCHEO_STACK_DIR is unset, fall back to ~/.orcheo/stack."""
    monkeypatch.delenv("ORCHEO_STACK_DIR", raising=False)
    result = _resolve_stack_project_dir()
    assert result == Path.home() / ".orcheo" / "stack"


def test_run_stack_command_defaults_expected_exit_codes(
    monkeypatch: Any,
) -> None:
    """expected_exit_codes defaults to {0} when not provided."""
    executed: list[str] = []

    def _run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        del check
        executed[:] = command
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("orcheo_sdk.cli.main.subprocess.run", _run)
    _run_stack_command(["echo", "hello"], console=Console())
    assert executed == ["echo", "hello"]


def test_run_stack_command_raises_on_unexpected_exit_code(
    monkeypatch: Any,
) -> None:
    """Non-zero exit code not in expected set raises BadParameter."""

    def _run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        del check
        return subprocess.CompletedProcess(command, 42)

    monkeypatch.setattr("orcheo_sdk.cli.main.subprocess.run", _run)
    with pytest.raises(typer.BadParameter, match="exit code 42"):
        _run_stack_command(["false"], console=Console())


def test_stack_no_action_raises_error(
    runner: Any,
    env: dict[str, str],
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Invoking stack without any action flag shows an error."""
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir()
    (stack_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr("orcheo_sdk.cli.main.shutil.which", lambda _: "/usr/bin/docker")

    result = runner.invoke(
        app,
        ["--no-update-check", "stack"],
        env=_stack_env(env, stack_dir),
    )

    assert result.exit_code == 2
