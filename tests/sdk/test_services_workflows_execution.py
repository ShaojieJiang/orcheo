"""Workflow execution helpers tests."""

from __future__ import annotations
from types import SimpleNamespace
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.services.workflows import execution


def test_run_workflow_data_requires_version_identifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_workflow_data raises when the latest version lacks an id."""

    client = SimpleNamespace(base_url="https://api.local")
    monkeypatch.setattr(
        execution,
        "get_latest_workflow_version_data",
        lambda *_args, **_kwargs: {"id": ""},
    )

    with pytest.raises(CLIError, match="missing an id field"):
        execution.run_workflow_data(client, workflow_id="wf-123", service_token=None)
