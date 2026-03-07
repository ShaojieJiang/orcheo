"""MCP server for Orcheo CLI.

This module provides a Model Context Protocol (MCP) server that exposes
Orcheo CLI commands as tools, allowing AI agents to interact with Orcheo
workflows programmatically.
"""

from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from orcheo_sdk.mcp_server.main import create_server


def __getattr__(name: str) -> object:
    """Lazy import to avoid circular imports and pydantic conflicts."""
    if name == "create_server":
        from orcheo_sdk.mcp_server.main import create_server

        return create_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["create_server"]
