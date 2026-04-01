"""Unit tests for shared provider helpers."""

from __future__ import annotations
from pathlib import Path
import pytest
from orcheo.external_agents.models import AuthStatus
from orcheo.external_agents.providers.base import NpmCliProvider


class DummyProvider(NpmCliProvider):
    name = "dummy"
    display_name = "Dummy"
    package_name = "@tests/dummy"
    executable_name = "dummy-cli"

    def install_command(self, install_prefix: Path) -> list[str]:
        return ["npm", "install", "dummy", str(install_prefix)]

    def version_command(self, runtime):
        return ["dummy", "--version"]


def test_parse_version_reports_semver() -> None:
    provider = DummyProvider()
    version = provider.parse_version("dummy 1.2.3", "")
    assert version == "1.2.3"


def test_parse_version_errors_without_semver() -> None:
    provider = DummyProvider()
    with pytest.raises(ValueError, match="Could not parse"):  # type: ignore[call-arg]
        provider.parse_version("missing", "output")


def test_build_environment_merges_env(monkeypatch) -> None:
    provider = DummyProvider()
    monkeypatch.setenv("SOME_VAR", "original")
    merged = provider.build_environment({"SOME_VAR": "override", "NEW_VAR": "value"})

    assert merged["SOME_VAR"] == "override"
    assert merged["NEW_VAR"] == "value"


def test_install_command_and_executable_path_use_expected_layout(
    tmp_path: Path,
) -> None:
    provider = DummyProvider()

    assert NpmCliProvider.install_command(provider, tmp_path) == [
        "npm",
        "install",
        "--global",
        provider.package_name,
        "--prefix",
        str(tmp_path),
    ]
    assert NpmCliProvider.executable_path(provider, tmp_path) == (
        tmp_path / "bin" / provider.executable_name
    )


def test_build_environment_without_overrides_uses_process_environment(
    monkeypatch,
) -> None:
    provider = DummyProvider()
    monkeypatch.setenv("BASE_ONLY", "1")

    merged = provider.build_environment()

    assert merged["BASE_ONLY"] == "1"


def test_authenticated_if_env_var_present(tmp_path: Path) -> None:
    provider = DummyProvider()
    result = provider._authenticated_if_env_present(
        message="",
        commands=["cmd"],
        environ={"TOKEN": "secret"},
        env_var_names=("TOKEN",),
    )
    assert result.status == AuthStatus.AUTHENTICATED


def test_authenticated_if_file_present(tmp_path: Path) -> None:
    provider = DummyProvider()
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")

    result = provider._authenticated_if_env_present(
        message="",
        commands=["cmd"],
        environ={},
        env_var_names=("MISSING",),
        auth_files=(auth_file,),
    )

    assert result.status == AuthStatus.AUTHENTICATED


def test_authenticated_if_missing_returns_setup_needed() -> None:
    provider = DummyProvider()

    result = provider._authenticated_if_env_present(
        message="setup",
        commands=["cmd"],
        environ={"OTHER": ""},
        env_var_names=("TOKEN",),
    )

    assert result.status == AuthStatus.SETUP_NEEDED
    assert result.message == "setup"
    assert result.commands == ["cmd"]
