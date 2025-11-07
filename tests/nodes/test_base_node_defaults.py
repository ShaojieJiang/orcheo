"""Tests for BaseNode default tool method implementations."""

from __future__ import annotations
import pytest
from orcheo.nodes.base import BaseNode


class MinimalNode(BaseNode):
    """Minimal node for testing base methods."""

    pass


@pytest.mark.asyncio
async def test_base_node_tool_methods_default() -> None:
    node = MinimalNode(name="minimal")

    assert node.tool_run("arg") is None
    result = await node.tool_arun("arg")
    assert result is None
