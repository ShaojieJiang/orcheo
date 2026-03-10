"""Tests for workflow reminder helpers."""

from __future__ import annotations
from types import SimpleNamespace
import pytest
from orcheo_sdk.cli.workflow import reminders


def test_fetch_workflow_vault_readiness_returns_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    def fake_readiness(client: SimpleNamespace, workflow_id: str) -> dict[str, str]:
        captured.append(workflow_id)
        return {"missing_credentials": "secret"}

    monkeypatch.setattr(
        reminders,
        "get_workflow_credential_readiness_data",
        fake_readiness,
    )

    client = SimpleNamespace()
    result = reminders.fetch_workflow_vault_readiness(client, "wf-1")

    assert result == {"missing_credentials": "secret"}
    assert captured == ["wf-1"]


def test_fetch_workflow_vault_readiness_returns_none_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raising(*_args, **_kwargs) -> None:
        raise ValueError("nope")

    monkeypatch.setattr(
        reminders,
        "get_workflow_credential_readiness_data",
        raising,
    )

    client = SimpleNamespace()
    assert reminders.fetch_workflow_vault_readiness(client, "wf-2") is None
