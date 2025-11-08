"""MCP server entry point for Orcheo CLI."""

from importlib import import_module
from fastmcp import FastMCP
from orcheo_sdk.mcp_server import agent_tool_bindings as _agent_tool_bindings
from orcheo_sdk.mcp_server import codegen_tools as _codegen_tools
from orcheo_sdk.mcp_server import credential_tools as _credential_tools
from orcheo_sdk.mcp_server import node_tools as _node_tools
from orcheo_sdk.mcp_server import service_token_tools as _service_token_tools
from orcheo_sdk.mcp_server import workflow_tools as _workflow_tools
from orcheo_sdk.mcp_server.server import (
    create_server as _create_server,
)
from orcheo_sdk.mcp_server.server import (
    mcp,
    run_server,
)


# Modules that register MCP tools via decorators.
_TOOL_MODULES: tuple[str, ...] = (
    "orcheo_sdk.mcp_server.workflow_tools",
    "orcheo_sdk.mcp_server.node_tools",
    "orcheo_sdk.mcp_server.credential_tools",
    "orcheo_sdk.mcp_server.codegen_tools",
    "orcheo_sdk.mcp_server.agent_tool_bindings",
    "orcheo_sdk.mcp_server.service_token_tools",
)


def _load_tool_modules() -> None:
    """Import all tool modules to ensure decorators register handlers."""
    for module in _TOOL_MODULES:
        import_module(module)


# Load tool modules as soon as the package is imported.
_load_tool_modules()


_MODULE_EXPORTS: tuple[tuple[object, tuple[str, ...]], ...] = (
    (
        _workflow_tools,
        (
            "list_workflows",
            "show_workflow",
            "publish_workflow",
            "rotate_publish_token",
            "unpublish_workflow",
            "run_workflow",
            "delete_workflow",
            "upload_workflow",
            "download_workflow",
        ),
    ),
    (_node_tools, ("list_nodes", "show_node")),
    (
        _credential_tools,
        ("list_credentials", "create_credential", "delete_credential"),
    ),
    (
        _codegen_tools,
        ("generate_workflow_scaffold", "generate_workflow_template"),
    ),
    (_agent_tool_bindings, ("list_agent_tools", "show_agent_tool")),
    (
        _service_token_tools,
        (
            "list_service_tokens",
            "show_service_token",
            "create_service_token",
            "rotate_service_token",
            "revoke_service_token",
        ),
    ),
)


for module, exports in _MODULE_EXPORTS:
    for name in exports:
        globals()[name] = getattr(module, name)


_EXPORTED_NAMES: tuple[str, ...] = tuple(
    name for _, exports in _MODULE_EXPORTS for name in exports
)


__all__ = [
    "create_server",
    "main",
    "mcp",
]
__all__.extend(_EXPORTED_NAMES)


def create_server() -> FastMCP:
    """Create and configure the Orcheo MCP server."""
    return _create_server()


def main() -> None:
    """Run the MCP server (CLI entry point)."""
    run_server()


if __name__ == "__main__":  # pragma: no cover
    main()
