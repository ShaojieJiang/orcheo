"""Tests for MCP wrapper functions exposing agent tools."""

from __future__ import annotations


def test_mcp_list_agent_tools(mock_env: None) -> None:
    """Test list_agent_tools MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    result = main_module.list_agent_tools.fn()
    assert isinstance(result, list)


def test_mcp_show_agent_tool(mock_env: None) -> None:
    """Test show_agent_tool MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    class TestTool:
        """Simple test tool."""

        pass

    test_meta = ToolMetadata(
        name="test_tool_mcp",
        description="Test tool for MCP wrapper",
        category="test",
    )

    tool_registry._tools["test_tool_mcp"] = TestTool()  # type: ignore[assignment]
    tool_registry._metadata["test_tool_mcp"] = test_meta

    try:
        result = main_module.show_agent_tool.fn("test_tool_mcp")
        assert result["name"] == "test_tool_mcp"
    finally:
        tool_registry._tools.pop("test_tool_mcp", None)
        tool_registry._metadata.pop("test_tool_mcp", None)
