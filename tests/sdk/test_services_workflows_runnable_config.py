"""Workflow runnable-config service tests."""

from __future__ import annotations
from types import SimpleNamespace
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.services.workflows import runnable_config


def test_resolve_version_number_requires_existing_versions() -> None:
    """Resolve helper fails clearly when no workflow versions exist."""
    client = SimpleNamespace(get=lambda _path: [])

    with pytest.raises(CLIError, match="has no versions"):
        runnable_config._resolve_version_number(
            client,
            "wf-1",
            version=None,
        )


def test_resolve_version_number_rejects_invalid_version_payload() -> None:
    """Resolve helper validates resolved version payload shape."""
    client = SimpleNamespace(get=lambda _path: [{"id": "ver-1", "version": "1"}])

    with pytest.raises(CLIError, match="invalid version payload"):
        runnable_config._resolve_version_number(
            client,
            "wf-1",
            version=None,
        )


def test_save_workflow_runnable_config_wraps_put_errors() -> None:
    """Save helper wraps API write failures with contextual CLI errors."""

    def fail_put(_path: str, *, json_body: dict[str, object]) -> dict[str, object]:
        del json_body
        raise RuntimeError("upstream error")

    client = SimpleNamespace(put=fail_put)

    with pytest.raises(CLIError, match="Failed to save runnable config"):
        runnable_config.save_workflow_runnable_config_data(
            client,
            "wf-1",
            runnable_config={"tags": ["x"]},
            actor="cli",
            version=2,
        )
