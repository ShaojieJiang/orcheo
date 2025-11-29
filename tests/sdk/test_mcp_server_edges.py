"""Tests for MCP server edge tools."""

from __future__ import annotations


def test_mcp_list_edges(mock_env: None) -> None:
    """Test list_edges MCP tool wrapper."""
    from orcheo_sdk.mcp_server import edge_tools

    result = edge_tools.list_edges.fn()
    assert isinstance(result, list)
    assert len(result) > 0
    for edge in result:
        assert "name" in edge
        assert "category" in edge
        assert "description" in edge


def test_mcp_list_edges_with_category(mock_env: None) -> None:
    """Test list_edges MCP tool wrapper with category filter."""
    from orcheo_sdk.mcp_server import edge_tools
    from orcheo.edges.registry import EdgeMetadata, edge_registry

    test_meta = EdgeMetadata(
        name="TestFilterEdge",
        description="Test edge for filtering",
        category="filter_test",
    )
    edge_registry._edges["TestFilterEdge"] = lambda: None
    edge_registry._metadata["TestFilterEdge"] = test_meta

    try:
        result = edge_tools.list_edges.fn(category="filter_test")
        assert isinstance(result, list)
        names = [edge["name"] for edge in result]
        assert "TestFilterEdge" in names
    finally:
        edge_registry._edges.pop("TestFilterEdge", None)
        edge_registry._metadata.pop("TestFilterEdge", None)


def test_mcp_show_edge(mock_env: None) -> None:
    """Test show_edge MCP tool wrapper."""
    from orcheo_sdk.mcp_server import edge_tools
    from pydantic import BaseModel
    from orcheo.edges.registry import EdgeMetadata, edge_registry

    class TestEdgeShow(BaseModel):
        """Test edge for show."""

        field: str

    test_meta = EdgeMetadata(
        name="TestEdgeShow",
        description="Test edge",
        category="test",
    )
    edge_registry._edges["TestEdgeShow"] = TestEdgeShow
    edge_registry._metadata["TestEdgeShow"] = test_meta

    try:
        result = edge_tools.show_edge.fn(name="TestEdgeShow")
        assert result["name"] == "TestEdgeShow"
        assert "schema" in result
    finally:
        edge_registry._edges.pop("TestEdgeShow", None)
        edge_registry._metadata.pop("TestEdgeShow", None)


def test_mcp_tools_list_edges_wrapper(mock_env: None) -> None:
    """Test MCP tools.list_edges wrapper."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_edges()
    assert isinstance(result, list)


def test_mcp_tools_show_edge_wrapper(mock_env: None) -> None:
    """Test MCP tools.show_edge wrapper."""
    from orcheo_sdk.mcp_server import tools
    from pydantic import BaseModel
    from orcheo.edges.registry import EdgeMetadata, edge_registry

    class TestEdgeTools(BaseModel):
        """Test edge for tools wrapper."""

        value: int

    test_meta = EdgeMetadata(
        name="TestEdgeTools",
        description="Test edge",
        category="test",
    )
    edge_registry._edges["TestEdgeTools"] = TestEdgeTools
    edge_registry._metadata["TestEdgeTools"] = test_meta

    try:
        result = tools.show_edge(name="TestEdgeTools")
        assert result["name"] == "TestEdgeTools"
    finally:
        edge_registry._edges.pop("TestEdgeTools", None)
        edge_registry._metadata.pop("TestEdgeTools", None)
