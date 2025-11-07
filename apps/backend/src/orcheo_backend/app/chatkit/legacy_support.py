"""Helper utilities for bridging to the legacy ChatKit module."""

from __future__ import annotations
from collections.abc import Mapping
from importlib import import_module
from types import ModuleType
from typing import Any


def _legacy_module() -> ModuleType:
    """Return the compatibility module for legacy ChatKit imports."""
    return import_module("orcheo_backend.app.chatkit_service")


def call_get_settings() -> Any:
    """Retrieve settings via the legacy module so tests can patch it."""
    return _legacy_module().get_settings()


def call_build_graph(graph_config: Mapping[str, Any]) -> Any:
    """Build a graph via the legacy module to keep patch hooks working."""
    return _legacy_module().build_graph(graph_config)


__all__ = ["call_build_graph", "call_get_settings"]
