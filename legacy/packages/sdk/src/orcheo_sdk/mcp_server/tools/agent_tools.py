"""Agent tool discovery MCP tools."""

from __future__ import annotations
import logging
from functools import lru_cache
from importlib import import_module, util
from typing import Any
from orcheo_sdk.cli.errors import CLIError


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _ensure_agent_tools_registered() -> None:
    """Import agent tool modules so they register with the catalog."""
    from orcheo_sdk.mcp_server import tools as tools_module

    module_name = "orcheo.nodes.agent_tools.tools"

    util_module = getattr(tools_module, "util", util)
    logger_obj = getattr(tools_module, "logger", logger)
    import_module_fn = getattr(tools_module, "import_module", import_module)

    spec = util_module.find_spec(module_name)
    if spec is None:
        logger_obj.warning(
            "Optional agent tools module '%s' could not be found. "
            "Install orcheo agent tool plugins to enable additional tools.",
            module_name,
        )
        return

    try:
        import_module_fn(module_name)
    except Exception:  # pragma: no cover - defensive logging
        logger_obj.exception(
            "Failed to import optional agent tools module '%s'.",
            module_name,
        )


def list_agent_tools(category: str | None = None) -> list[dict[str, Any]]:
    """List registered agent tools with metadata."""
    from orcheo.nodes.agent_tools.registry import tool_registry

    _ensure_agent_tools_registered()

    entries = tool_registry.list_metadata()

    if category:
        lowered = category.lower()
        entries = [
            item
            for item in entries
            if lowered in item.category.lower() or lowered in item.name.lower()
        ]

    return [
        {
            "name": item.name,
            "category": item.category,
            "description": item.description,
        }
        for item in entries
    ]


def show_agent_tool(name: str) -> dict[str, Any]:
    """Display metadata and schema information for an agent tool."""
    from orcheo.nodes.agent_tools.registry import tool_registry

    _ensure_agent_tools_registered()

    metadata = tool_registry.get_metadata(name)
    tool = tool_registry.get_tool(name)

    if metadata is None or tool is None:
        raise CLIError(f"Agent tool '{name}' is not registered.")

    result: dict[str, Any] = {
        "name": metadata.name,
        "category": metadata.category,
        "description": metadata.description,
    }

    schema_data: dict[str, Any] = {}
    if hasattr(tool, "args_schema") and tool.args_schema is not None:
        if hasattr(tool.args_schema, "model_json_schema"):
            schema_data = tool.args_schema.model_json_schema()
    elif hasattr(tool, "model_json_schema"):
        schema_data = tool.model_json_schema()

    if schema_data:
        result["schema"] = schema_data

    return result


__all__ = ["list_agent_tools", "show_agent_tool"]
