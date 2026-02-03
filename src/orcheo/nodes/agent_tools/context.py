"""Context for agent tool execution."""

from __future__ import annotations
from collections.abc import Awaitable, Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from langchain_core.runnables import RunnableConfig


ToolProgressCallback = Callable[[Mapping[str, Any]], Awaitable[None]]

_ACTIVE_TOOL_CONFIG: ContextVar[RunnableConfig | None] = ContextVar(
    "orcheo_active_tool_config", default=None
)
_ACTIVE_TOOL_PROGRESS_CALLBACK: ContextVar[ToolProgressCallback | None] = ContextVar(
    "orcheo_active_tool_progress_callback", default=None
)


@contextmanager
def tool_execution_context(config: RunnableConfig | None) -> Any:
    """Bind a RunnableConfig for tool executions within this context."""
    token = _ACTIVE_TOOL_CONFIG.set(config)
    try:
        yield config
    finally:
        _ACTIVE_TOOL_CONFIG.reset(token)


@contextmanager
def tool_progress_context(callback: ToolProgressCallback | None) -> Any:
    """Bind a progress callback for tool executions within this context."""
    token = _ACTIVE_TOOL_PROGRESS_CALLBACK.set(callback)
    try:
        yield callback
    finally:
        _ACTIVE_TOOL_PROGRESS_CALLBACK.reset(token)


def get_active_tool_config() -> RunnableConfig | None:
    """Return the currently bound tool execution config, if any."""
    return _ACTIVE_TOOL_CONFIG.get()


def get_active_tool_progress_callback() -> ToolProgressCallback | None:
    """Return the currently bound tool progress callback, if any."""
    return _ACTIVE_TOOL_PROGRESS_CALLBACK.get()


__all__ = [
    "ToolProgressCallback",
    "get_active_tool_config",
    "get_active_tool_progress_callback",
    "tool_execution_context",
    "tool_progress_context",
]
