"""Formatting helpers for workflow export."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from orcheo_sdk.cli.errors import CLIError


def _format_workflow_as_python(
    workflow: Mapping[str, Any], graph: Mapping[str, Any]
) -> str:
    """Format workflow configuration as Python source."""
    if graph.get("format") == "langgraph-script" and "source" in graph:
        source = graph["source"]
        if isinstance(source, str) and source.strip():
            return source
    observed_format = graph.get("format", "unknown")
    workflow_name = workflow.get("name", "workflow")
    msg = (
        f"Workflow '{workflow_name}' uses unsupported format '{observed_format}'. "
        "Only LangGraph script versions can be downloaded. Re-ingest from a "
        "Python script and try again."
    )
    raise CLIError(msg)


__all__ = ["_format_workflow_as_python"]
