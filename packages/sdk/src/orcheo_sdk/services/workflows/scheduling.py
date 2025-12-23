"""Workflow cron scheduling helpers."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from orcheo.graph.ingestion.config import LANGGRAPH_SCRIPT_FORMAT
from orcheo.triggers.cron import CronTriggerConfig
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.http import ApiClient
from orcheo_sdk.services.workflows.versions import get_latest_workflow_version_data


def schedule_workflow_cron(
    client: ApiClient,
    workflow_id: str,
) -> dict[str, Any]:
    """Configure cron scheduling for the workflow based on its latest version."""
    version = get_latest_workflow_version_data(client, workflow_id)
    graph = version.get("graph")
    if not isinstance(graph, Mapping):
        raise CLIError("Latest workflow version is missing graph data.")

    cron_config = _extract_cron_config(graph)
    if cron_config is None:
        return {
            "status": "noop",
            "message": f"Workflow '{workflow_id}' has no cron trigger to schedule.",
        }

    payload = cron_config.model_dump(mode="json")
    response = client.put(
        f"/api/workflows/{workflow_id}/triggers/cron/config",
        json_body=payload,
    )
    return {
        "status": "scheduled",
        "message": f"Cron trigger scheduled for workflow '{workflow_id}'.",
        "config": response or payload,
    }


def unschedule_workflow_cron(
    client: ApiClient,
    workflow_id: str,
) -> dict[str, Any]:
    """Remove cron scheduling for the workflow."""
    client.delete(f"/api/workflows/{workflow_id}/triggers/cron/config")
    return {
        "status": "unscheduled",
        "message": f"Cron trigger unscheduled for workflow '{workflow_id}'.",
    }


def _extract_cron_config(graph: Mapping[str, Any]) -> CronTriggerConfig | None:
    """Return the cron trigger config if the workflow contains one."""
    nodes = _extract_nodes(graph)
    cron_nodes = [node for node in nodes if node.get("type") == "CronTriggerNode"]
    if not cron_nodes:
        return None
    if len(cron_nodes) > 1:
        raise CLIError("Workflow contains multiple cron triggers.")

    node = cron_nodes[0]
    config_payload: dict[str, Any] = {}
    expression = node.get("expression")
    if isinstance(expression, str) and expression.strip():
        config_payload["expression"] = expression
    timezone = node.get("timezone")
    if isinstance(timezone, str) and timezone.strip():
        config_payload["timezone"] = timezone
    if "allow_overlapping" in node:
        config_payload["allow_overlapping"] = bool(node.get("allow_overlapping"))
    if "start_at" in node:
        config_payload["start_at"] = node.get("start_at")
    if "end_at" in node:
        config_payload["end_at"] = node.get("end_at")
    return CronTriggerConfig(**config_payload)


def _extract_nodes(graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return the serialized nodes list from a workflow graph payload."""
    graph_format = graph.get("format")
    if graph_format in {LANGGRAPH_SCRIPT_FORMAT, "langgraph_script"}:
        summary = graph.get("summary")
        if isinstance(summary, Mapping):
            nodes = summary.get("nodes")
            if isinstance(nodes, list):
                return [node for node in nodes if isinstance(node, Mapping)]
        return []

    nodes = graph.get("nodes")
    if isinstance(nodes, list):
        return [node for node in nodes if isinstance(node, Mapping)]
    return []


__all__ = ["schedule_workflow_cron", "unschedule_workflow_cron"]
