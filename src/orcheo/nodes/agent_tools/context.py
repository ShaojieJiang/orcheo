"""Context for agent tool execution."""

from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from langchain_core.runnables import RunnableConfig


_ACTIVE_TOOL_CONFIG: ContextVar[RunnableConfig | None] = ContextVar(
    "orcheo_active_tool_config", default=None
)


@contextmanager
def tool_execution_context(config: RunnableConfig | None) -> Any:
    """Bind a RunnableConfig for tool executions within this context."""
    token = _ACTIVE_TOOL_CONFIG.set(config)
    try:
        yield config
    finally:
        _ACTIVE_TOOL_CONFIG.reset(token)


def get_active_tool_config() -> RunnableConfig | None:
    """Return the currently bound tool execution config, if any."""
    return _ACTIVE_TOOL_CONFIG.get()


__all__ = ["get_active_tool_config", "tool_execution_context"]
