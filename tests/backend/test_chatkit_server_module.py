"""Unit tests for the ChatKit server module-level helpers."""

from __future__ import annotations
from typing import Any
import pytest
from orcheo_backend.app.chatkit import server as server_module


def test_call_build_graph_forwards_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """_call_build_graph should proxy directly to the legacy helper."""
    sentinel = object()
    captured: dict[str, Any] = {}

    def fake_build(graph_config: dict[str, Any]) -> object:
        captured["config"] = graph_config
        return sentinel

    monkeypatch.setattr(server_module, "call_build_graph", fake_build)

    graph_config = {"format": "test", "source": "code"}
    result = server_module._call_build_graph(graph_config)

    assert result is sentinel
    assert captured["config"] is graph_config
