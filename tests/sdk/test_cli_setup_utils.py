"""Tests for CLI setup helper utilities."""

from __future__ import annotations
import pytest
import typer
from rich.console import Console
from orcheo_sdk.cli import setup as setup_mod


class _MissingOsReleasePath:
    """Fake Path that always reports /etc/os-release as missing."""

    def __init__(self, path: str) -> None:
        self._path = path

    def exists(self) -> bool:
        return False

    def read_text(self, *, encoding: str) -> str:
        raise AssertionError("read_text should not be called when path is absent")


def test_read_os_release_missing_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_mod, "Path", _MissingOsReleasePath)
    assert setup_mod._read_os_release() == {}


def test_run_privileged_command_runs_without_sudo_when_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(setup_mod.os, "geteuid", lambda: 0)
    recorded: list[list[str]] = []

    def _fake_run(command: list[str], *, console: Console) -> None:
        recorded.append(command)

    monkeypatch.setattr(setup_mod, "_run_command", _fake_run)
    setup_mod._run_privileged_command(["/bin/true"], console=Console(record=True))
    assert recorded == [["/bin/true"]]


def test_run_privileged_command_rejects_without_sudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(setup_mod.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(setup_mod, "_has_binary", lambda _: False)
    with pytest.raises(typer.BadParameter):
        setup_mod._run_privileged_command(["/bin/true"], console=Console(record=True))


def test_run_privileged_command_prefixes_with_sudo_when_needed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(setup_mod.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(setup_mod, "_has_binary", lambda name: name == "sudo")
    recorded: list[list[str]] = []

    def _fake_run(command: list[str], *, console: Console) -> None:
        recorded.append(command)

    monkeypatch.setattr(setup_mod, "_run_command", _fake_run)
    setup_mod._run_privileged_command(["/bin/true"], console=Console(record=True))
    assert recorded == [["sudo", "/bin/true"]]


def test_current_shell_has_docker_access_false_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(setup_mod, "_has_binary", lambda name: False)
    assert not setup_mod._current_shell_has_docker_access()


def test_current_shell_has_docker_access_true_when_docker_info_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(setup_mod, "_has_binary", lambda name: True)

    class _Result:
        returncode = 0

    monkeypatch.setattr(
        setup_mod.subprocess,
        "run",
        lambda *args, **kwargs: _Result(),
    )
    assert setup_mod._current_shell_has_docker_access()


def test_attempt_docker_autoinstall_runs_commands_when_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        setup_mod, "_is_supported_docker_autoinstall_linux", lambda: True
    )
    monkeypatch.setattr(
        setup_mod,
        "_has_binary",
        lambda name: name in {"apt-get", "docker"},
    )
    calls: list[list[str]] = []

    def _fake_run(command: list[str], *, console: Console) -> None:
        calls.append(command)

    monkeypatch.setattr(setup_mod, "_run_privileged_command", _fake_run)
    monkeypatch.setattr(setup_mod, "_current_username", lambda: "alice")

    assert setup_mod._attempt_docker_autoinstall(console=Console(record=True))
    assert calls[:3] == [
        ["apt-get", "update"],
        ["apt-get", "install", "-y", "docker.io", "docker-compose-v2"],
        ["systemctl", "enable", "--now", "docker"],
    ]
    assert calls[3] == ["usermod", "-aG", "docker", "alice"]


def test_attempt_docker_autoinstall_handles_privileged_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        setup_mod, "_is_supported_docker_autoinstall_linux", lambda: True
    )
    monkeypatch.setattr(setup_mod, "_has_binary", lambda _: True)

    def _fake_run(*args: object, **kwargs: object) -> None:
        raise typer.BadParameter("boom")

    monkeypatch.setattr(setup_mod, "_run_privileged_command", _fake_run)
    assert not setup_mod._attempt_docker_autoinstall(console=Console(record=True))


def test_attempt_docker_autoinstall_returns_false_when_docker_still_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        setup_mod, "_is_supported_docker_autoinstall_linux", lambda: True
    )

    def _fake_has_binary(name: str) -> bool:
        return name == "apt-get"

    monkeypatch.setattr(setup_mod, "_has_binary", _fake_has_binary)
    monkeypatch.setattr(
        setup_mod, "_run_privileged_command", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(setup_mod, "_current_username", lambda: None)

    assert not setup_mod._attempt_docker_autoinstall(console=Console(record=True))
