"""Tests for MCP server node discovery endpoints."""

from __future__ import annotations
import pytest
from orcheo_sdk.cli.errors import CLIError


def test_list_nodes(mock_env: None) -> None:
    """Test listing nodes."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_nodes()
    assert isinstance(result, list)
    assert len(result) > 0
    node_names = [node["name"] for node in result]
    assert "WebhookTriggerNode" in node_names


def test_list_nodes_with_tag_filter(mock_env: None) -> None:
    """Test listing nodes with tag filter."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_nodes(tag="trigger")
    assert isinstance(result, list)
    for node in result:
        assert (
            "trigger" in node["name"].lower() or "trigger" in node["category"].lower()
        )


def test_show_node_success(mock_env: None) -> None:
    """Test showing node details."""
    from orcheo_sdk.mcp_server import tools

    result = tools.show_node("WebhookTriggerNode")
    assert result["name"] == "WebhookTriggerNode"
    assert "category" in result
    assert "description" in result
    assert "schema" in result


def test_show_node_not_found(mock_env: None) -> None:
    """Test showing non-existent node."""
    from orcheo_sdk.mcp_server import tools

    with pytest.raises(CLIError, match="not registered"):
        tools.show_node("NonExistentNode")


def test_show_node_with_attributes_only(mock_env: None) -> None:
    """Test showing node that has attributes but no model_json_schema."""
    from orcheo.nodes.registry import NodeMetadata, registry

    test_meta = NodeMetadata(
        name="TestNodeWithAttrs",
        description="Test node with attributes",
        category="test",
    )

    class TestNodeWithAttrs:
        """Node with annotations but no model_json_schema."""

        test_attr: str
        count: int

    registry._nodes["TestNodeWithAttrs"] = TestNodeWithAttrs
    registry._metadata["TestNodeWithAttrs"] = test_meta

    try:
        from orcheo_sdk.mcp_server import tools

        result = tools.show_node("TestNodeWithAttrs")
        assert result["name"] == "TestNodeWithAttrs"
        assert "attributes" in result
        assert "test_attr" in result["attributes"]
        assert "count" in result["attributes"]
    finally:
        registry._nodes.pop("TestNodeWithAttrs", None)
        registry._metadata.pop("TestNodeWithAttrs", None)


def test_mcp_list_nodes(mock_env: None) -> None:
    """Test list_nodes MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    result = main_module.list_nodes.fn()
    assert isinstance(result, list)


def test_mcp_show_node(mock_env: None) -> None:
    """Test show_node MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    result = main_module.show_node.fn("WebhookTriggerNode")
    assert result["name"] == "WebhookTriggerNode"
