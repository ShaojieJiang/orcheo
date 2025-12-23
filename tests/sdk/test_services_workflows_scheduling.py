"""Workflow cron scheduling service tests."""

from __future__ import annotations
from datetime import UTC, datetime
from types import SimpleNamespace
import pytest
from orcheo.graph.ingestion.config import LANGGRAPH_SCRIPT_FORMAT
from orcheo.triggers.cron import CronTriggerConfig
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


def test_schedule_workflow_cron_requires_graph_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduling fails when the latest workflow version lacks graph data."""

    monkeypatch.setattr(
        scheduling,
        "get_latest_workflow_version_data",
        lambda *_args, **_kwargs: {"graph": "not-a-map"},
    )

    with pytest.raises(CLIError, match="missing graph data"):
        scheduling.schedule_workflow_cron(SimpleNamespace(), workflow_id="wf-123")


def test_extract_cron_config_populates_optional_fields() -> None:
    """Cron trigger config copies optional fields when they are provided."""

    start_at = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    end_at = datetime(2025, 1, 2, 0, 0, tzinfo=UTC)
    graph = {
        "nodes": [
            {
                "type": "CronTriggerNode",
                "expression": "0 1 * * *",
                "timezone": "America/New_York",
                "allow_overlapping": True,
                "start_at": start_at,
                "end_at": end_at,
            }
        ]
    }

    config = scheduling._extract_cron_config(graph)
    assert config is not None
    assert config.expression == "0 1 * * *"
    assert config.timezone == "America/New_York"
    assert config.allow_overlapping is True
    assert config.start_at == start_at
    assert config.end_at == end_at


def test_extract_nodes_returns_empty_for_summary_without_nodes() -> None:
    graph = {"format": "langgraph_script", "summary": {"nodes": "invalid"}}
    assert scheduling._extract_nodes(graph) == []


def test_extract_nodes_returns_empty_when_nodes_missing() -> None:
    graph = {"nodes": "not-a-list"}
    assert scheduling._extract_nodes(graph) == []


def test_extract_nodes_returns_summary_nodes_for_langgraph_format() -> None:
    graph = {
        "format": LANGGRAPH_SCRIPT_FORMAT,
        "summary": {"nodes": [{"id": "cron_node"}, 123]},
    }

    assert scheduling._extract_nodes(graph) == [{"id": "cron_node"}]


def test_extract_cron_config_uses_defaults_when_expression_and_timezone_blank() -> None:
    default_config = CronTriggerConfig()
    graph = {
        "nodes": [
            {
                "type": "CronTriggerNode",
                "expression": "    ",
                "timezone": "",
                "allow_overlapping": False,
            }
        ]
    }

    config = scheduling._extract_cron_config(graph)
    assert config is not None
    assert config.expression == default_config.expression
    assert config.timezone == default_config.timezone
    assert config.allow_overlapping is False
