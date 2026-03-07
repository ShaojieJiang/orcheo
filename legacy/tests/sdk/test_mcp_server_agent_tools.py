"""Tests for agent tool discovery through the MCP server."""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from orcheo_sdk.cli.errors import CLIError


def test_ensure_agent_tools_registered_success(mock_env: None) -> None:
    """Test _ensure_agent_tools_registered when module is found."""
    from orcheo_sdk.mcp_server.tools import _ensure_agent_tools_registered

    _ensure_agent_tools_registered.cache_clear()

    mock_spec = MagicMock()
    mock_spec.name = "orcheo.nodes.agent_tools.tools"

    with patch("orcheo_sdk.mcp_server.tools.util.find_spec", return_value=mock_spec):
        with patch("orcheo_sdk.mcp_server.tools.import_module") as mock_import:
            _ensure_agent_tools_registered()
            mock_import.assert_called_once_with("orcheo.nodes.agent_tools.tools")


def test_ensure_agent_tools_registered_not_found(mock_env: None) -> None:
    """Test _ensure_agent_tools_registered when module is not found."""
    from orcheo_sdk.mcp_server.tools import _ensure_agent_tools_registered

    _ensure_agent_tools_registered.cache_clear()

    with patch("orcheo_sdk.mcp_server.tools.util.find_spec", return_value=None):
        with patch("orcheo_sdk.mcp_server.tools.logger") as mock_logger:
            _ensure_agent_tools_registered()
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "orcheo.nodes.agent_tools.tools" in call_args[0][1]


def test_list_agent_tools_import_error(mock_env: None) -> None:
    """Test list_agent_tools handles ImportError gracefully."""
    import sys
    from orcheo_sdk.mcp_server import tools

    with patch.dict(sys.modules, {"orcheo.nodes.agent_tools.tools": None}):
        result = tools.list_agent_tools()
        assert isinstance(result, list)


def test_list_agent_tools(mock_env: None) -> None:
    """Test listing agent tools."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_agent_tools()
    assert isinstance(result, list)
    if result:
        assert "name" in result[0]
        assert "category" in result[0]


def test_list_agent_tools_with_category_filter(mock_env: None) -> None:
    """Test listing agent tools with category filter."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_agent_tools(category="test")
    assert isinstance(result, list)
    for tool in result:
        assert "test" in tool["name"].lower() or "test" in tool["category"].lower()


def test_show_agent_tool_import_error(mock_env: None) -> None:
    """Test show_agent_tool handles ImportError gracefully."""
    import sys
    from orcheo_sdk.mcp_server import tools

    with patch.dict(sys.modules, {"orcheo.nodes.agent_tools.tools": None}):
        with pytest.raises(CLIError, match="not registered"):
            tools.show_agent_tool("NonExistentTool")


def test_show_agent_tool_not_found(mock_env: None) -> None:
    """Test showing non-existent agent tool."""
    from orcheo_sdk.mcp_server import tools

    with pytest.raises(CLIError, match="not registered"):
        tools.show_agent_tool("NonExistentTool")


def test_show_agent_tool_with_schema(mock_env: None) -> None:
    """Test showing agent tool with schema extraction."""
    from pydantic import BaseModel
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    class TestSchema(BaseModel):
        """Test schema."""

        query: str
        count: int

    class TestTool:
        """Test tool with args_schema."""

        args_schema = TestSchema

    test_meta = ToolMetadata(
        name="test_tool_with_schema",
        description="Test tool with schema",
        category="test",
    )

    tool_registry._tools["test_tool_with_schema"] = TestTool()  # type: ignore[assignment]
    tool_registry._metadata["test_tool_with_schema"] = test_meta

    try:
        from orcheo_sdk.mcp_server import tools

        result = tools.show_agent_tool("test_tool_with_schema")
        assert result["name"] == "test_tool_with_schema"
        assert "schema" in result
    finally:
        tool_registry._tools.pop("test_tool_with_schema", None)
        tool_registry._metadata.pop("test_tool_with_schema", None)


def test_show_agent_tool_with_model_json_schema(mock_env: None) -> None:
    """Test showing agent tool with model_json_schema method."""
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    class TestToolWithModel:
        """Test tool with model_json_schema."""

        @staticmethod
        def model_json_schema() -> dict:
            return {"type": "object", "properties": {"query": {"type": "string"}}}

    test_meta = ToolMetadata(
        name="test_tool_model",
        description="Test tool with model schema",
        category="test",
    )

    tool_registry._tools["test_tool_model"] = TestToolWithModel()  # type: ignore[assignment]
    tool_registry._metadata["test_tool_model"] = test_meta

    try:
        from orcheo_sdk.mcp_server import tools

        result = tools.show_agent_tool("test_tool_model")
        assert result["name"] == "test_tool_model"
        assert "schema" in result
        assert result["schema"]["type"] == "object"
    finally:
        tool_registry._tools.pop("test_tool_model", None)
        tool_registry._metadata.pop("test_tool_model", None)


def test_show_agent_tool_no_schema(mock_env: None) -> None:
    """Test showing agent tool with no schema attributes."""
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    class TestToolNoSchema:
        """Test tool with no schema."""

        pass

    test_meta = ToolMetadata(
        name="test_tool_no_schema",
        description="Test tool without schema",
        category="test",
    )

    tool_registry._tools["test_tool_no_schema"] = TestToolNoSchema()  # type: ignore[assignment]
    tool_registry._metadata["test_tool_no_schema"] = test_meta

    try:
        from orcheo_sdk.mcp_server import tools

        result = tools.show_agent_tool("test_tool_no_schema")
        assert result["name"] == "test_tool_no_schema"
        assert "schema" not in result
    finally:
        tool_registry._tools.pop("test_tool_no_schema", None)
        tool_registry._metadata.pop("test_tool_no_schema", None)


def test_show_agent_tool_with_args_schema_no_method(mock_env: None) -> None:
    """Test showing agent tool with args_schema but no model_json_schema method."""
    from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry

    class FakeSchema:
        """Fake schema without model_json_schema."""

        pass

    class TestToolWithArgsSchemaNoMethod:
        """Test tool with args_schema but no model_json_schema."""

        args_schema = FakeSchema()

    test_meta = ToolMetadata(
        name="test_tool_args_no_method",
        description="Test tool with args_schema but no method",
        category="test",
    )

    tool_registry._tools["test_tool_args_no_method"] = TestToolWithArgsSchemaNoMethod()  # type: ignore[assignment]
    tool_registry._metadata["test_tool_args_no_method"] = test_meta

    try:
        from orcheo_sdk.mcp_server import tools

        result = tools.show_agent_tool("test_tool_args_no_method")
        assert result["name"] == "test_tool_args_no_method"
        assert "schema" not in result
    finally:
        tool_registry._tools.pop("test_tool_args_no_method", None)
        tool_registry._metadata.pop("test_tool_args_no_method", None)
