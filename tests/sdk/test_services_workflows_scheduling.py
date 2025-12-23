"""Workflow cron scheduling service tests."""

from __future__ import annotations
from types import SimpleNamespace
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.services.workflows import scheduling


def test_schedule_workflow_cron_noop_without_cron_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduling is a no-op when the workflow has no cron trigger."""

    monkeypatch.setattr(
        scheduling,
        "get_latest_workflow_version_data",
        lambda *_args, **_kwargs: {"graph": {"nodes": []}},
    )

    result = scheduling.schedule_workflow_cron(
        SimpleNamespace(),
        workflow_id="wf-123",
    )

    assert result["status"] == "noop"


def test_schedule_workflow_cron_configures_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduling uses the cron trigger configuration from the workflow."""

    graph = {
        "format": "langgraph_script",
        "summary": {
            "nodes": [
                {
                    "name": "cron_trigger",
                    "type": "CronTriggerNode",
                    "expression": "* * * * *",
                    "timezone": "UTC",
                    "allow_overlapping": False,
                    "start_at": None,
                    "end_at": None,
                }
            ]
        },
    }

    monkeypatch.setattr(
        scheduling,
        "get_latest_workflow_version_data",
        lambda *_args, **_kwargs: {"graph": graph},
    )

    captured: dict[str, object] = {}

    def fake_put(
        path: str, *, json_body: dict[str, object] | None = None
    ) -> dict[str, object]:
        captured["path"] = path
        captured["json_body"] = json_body
        return json_body or {}

    client = SimpleNamespace(put=fake_put)

    result = scheduling.schedule_workflow_cron(client, workflow_id="wf-123")

    assert result["status"] == "scheduled"
    assert captured["path"] == "/api/workflows/wf-123/triggers/cron/config"
    assert captured["json_body"]["expression"] == "* * * * *"


def test_schedule_workflow_cron_rejects_multiple_triggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduling fails when multiple cron triggers are present."""

    graph = {
        "nodes": [
            {"name": "cron_1", "type": "CronTriggerNode", "expression": "* * * * *"},
            {"name": "cron_2", "type": "CronTriggerNode", "expression": "0 * * * *"},
        ]
    }

    monkeypatch.setattr(
        scheduling,
        "get_latest_workflow_version_data",
        lambda *_args, **_kwargs: {"graph": graph},
    )

    with pytest.raises(CLIError, match="multiple cron triggers"):
        scheduling.schedule_workflow_cron(SimpleNamespace(), workflow_id="wf-123")


def test_unschedule_workflow_cron_calls_delete() -> None:
    """Unscheduling calls the API delete endpoint."""

    captured: dict[str, object] = {}

    def fake_delete(path: str) -> None:
        captured["path"] = path

    client = SimpleNamespace(delete=fake_delete)

    result = scheduling.unschedule_workflow_cron(client, workflow_id="wf-123")

    assert result["status"] == "unscheduled"
    assert captured["path"] == "/api/workflows/wf-123/triggers/cron/config"
