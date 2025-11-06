"""Formatting helpers for workflow export."""

from __future__ import annotations
import json
from collections.abc import Mapping
from typing import Any


def _format_workflow_as_json(
    workflow: Mapping[str, Any], graph: Mapping[str, Any]
) -> str:
    """Format workflow configuration as JSON."""
    output: dict[str, Any] = {
        "name": workflow.get("name"),
        "graph": graph,
    }
    if "metadata" in workflow:
        output["metadata"] = workflow["metadata"]

    return json.dumps(output, indent=2, ensure_ascii=False)


def _format_workflow_as_python(
    workflow: Mapping[str, Any], graph: Mapping[str, Any]
) -> str:
    """Format workflow configuration as Python code."""
    if graph.get("format") == "langgraph-script" and "source" in graph:
        return graph["source"]

    name = workflow.get("name", "workflow")
    nodes = graph.get("nodes", [])

    lines = [
        '"""Generated workflow configuration."""',
        "",
        "from orcheo_sdk import Workflow, WorkflowNode",
        "from pydantic import BaseModel",
        "",
        "",
    ]

    seen_types: set[str] = set()
    for node in nodes:
        node_type = node.get("type", "Unknown")
        if node_type in seen_types:
            continue
        seen_types.add(node_type)

        lines.extend(
            [
                f"class {node_type}Config(BaseModel):",
                "    # TODO: Define configuration fields",
                "    pass",
                "",
                "",
                f"class {node_type}Node(WorkflowNode[{node_type}Config]):",
                f'    type_name = "{node_type}"',
                "",
                "",
            ]
        )

    lines.extend(
        [
            f'workflow = Workflow(name="{name}")',
            "",
        ]
    )

    for node in nodes:
        node_name = node.get("name", "unknown")
        node_type = node.get("type", "Unknown")
        lines.append(
            f"# workflow.add_node({node_type}Node('{node_name}', {node_type}Config()))"
        )

    lines.append("")
    lines.append("# TODO: Configure node dependencies using depends_on parameter")
    lines.append("")

    return "\n".join(lines)


__all__ = [
    "_format_workflow_as_json",
    "_format_workflow_as_python",
]
