"""Tests for `orcheo install` commands."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.main import app


def test_install_command_non_interactive_defaults(
    runner: Any,
    monkeypatch: Any,
) -> None:
    calls: dict[str, object] = {}

    def _run_setup(**kwargs: object) -> object:
        calls.update(kwargs)
        from orcheo_sdk.cli.setup import SetupConfig

        return SetupConfig(
            mode="install",
            backend_url="http://localhost:8000",
            auth_mode="api-key",
            api_key="generated",
            chatkit_domain_key=None,
            start_local_stack=True,
            install_docker_if_missing=True,
        )

    monkeypatch.setattr("orcheo_sdk.cli.main.run_setup", _run_setup)
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.execute_setup", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.print_summary", lambda *args, **kwargs: None
    )

    result = runner.invoke(app, ["install", "--yes"])

    assert result.exit_code == 0
    assert calls["yes"] is True


def test_install_command_rejects_invalid_mode(runner: Any) -> None:
    result = runner.invoke(app, ["install", "--mode", "bad"])
    assert result.exit_code == 2


def test_install_command_respects_no_update_check(
    runner: Any,
    monkeypatch: Any,
) -> None:
    called = {"value": False}

    def _mark(**kwargs: object) -> None:
        called["value"] = True

    monkeypatch.setattr("orcheo_sdk.cli.main.maybe_print_update_notice", _mark)

    from orcheo_sdk.cli.setup import SetupConfig

    monkeypatch.setattr(
        "orcheo_sdk.cli.main.run_setup",
        lambda **kwargs: SetupConfig(
            mode="install",
            backend_url="http://localhost:8000",
            auth_mode="api-key",
            api_key="generated",
            chatkit_domain_key=None,
            start_local_stack=True,
            install_docker_if_missing=True,
        ),
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.execute_setup", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.print_summary", lambda *args, **kwargs: None
    )

    result = runner.invoke(app, ["--no-update-check", "install", "--yes"])

    assert result.exit_code == 0
    assert called["value"] is False


def test_install_upgrade_subcommand_forces_upgrade(
    runner: Any,
    monkeypatch: Any,
) -> None:
    captured_mode = {"value": None}

    def _run_setup(**kwargs: object) -> object:
        captured_mode["value"] = kwargs["mode"]
        from orcheo_sdk.cli.setup import SetupConfig

        return SetupConfig(
            mode="upgrade",
            backend_url="http://localhost:8000",
            auth_mode="api-key",
            api_key="generated",
            chatkit_domain_key=None,
            start_local_stack=True,
            install_docker_if_missing=True,
        )

    monkeypatch.setattr("orcheo_sdk.cli.main.run_setup", _run_setup)
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.execute_setup", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.print_summary", lambda *args, **kwargs: None
    )

    result = runner.invoke(app, ["install", "upgrade", "--yes"])
    assert result.exit_code == 0
    assert captured_mode["value"] == "upgrade"


def test_install_command_passes_chatkit_domain_key(
    runner: Any,
    monkeypatch: Any,
) -> None:
    captured_domain_key = {"value": None}

    def _run_setup(**kwargs: object) -> object:
        captured_domain_key["value"] = kwargs["chatkit_domain_key"]
        from orcheo_sdk.cli.setup import SetupConfig

        return SetupConfig(
            mode="install",
            backend_url="http://localhost:8000",
            auth_mode="api-key",
            api_key="generated",
            chatkit_domain_key="domain_pk_test",
            start_local_stack=False,
            install_docker_if_missing=True,
        )

    monkeypatch.setattr("orcheo_sdk.cli.main.run_setup", _run_setup)
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.execute_setup", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.main.print_summary", lambda *args, **kwargs: None
    )

    result = runner.invoke(
        app,
        ["install", "--yes", "--chatkit-domain-key", "domain_pk_test"],
    )

    assert result.exit_code == 0
    assert captured_domain_key["value"] == "domain_pk_test"
