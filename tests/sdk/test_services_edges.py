"""Tests for SDK edge service operations."""

from __future__ import annotations
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.services.edges import list_edges_data, show_edge_data


def test_list_edges_data_returns_all_edges(mock_env: None) -> None:
    """Test list_edges_data returns all registered edges."""
    result = list_edges_data()
    assert isinstance(result, list)
    assert len(result) > 0
    # Verify structure
    for edge in result:
        assert "name" in edge
        assert "category" in edge
        assert "description" in edge


def test_list_edges_data_with_category_filter(mock_env: None) -> None:
    """Test list_edges_data filters by category."""
    # Register a test edge to ensure we have something to filter
    from orcheo.edges.registry import EdgeMetadata, edge_registry

    test_meta = EdgeMetadata(
        name="TestControlEdge",
        description="Test control edge",
        category="control",
    )
    edge_registry._edges["TestControlEdge"] = lambda: None
    edge_registry._metadata["TestControlEdge"] = test_meta

    try:
        result = list_edges_data(category="control")
        assert isinstance(result, list)
        # All results should match the filter
        for edge in result:
            assert (
                "control" in edge["category"].lower()
                or "control" in edge["name"].lower()
            )
    finally:
        edge_registry._edges.pop("TestControlEdge", None)
        edge_registry._metadata.pop("TestControlEdge", None)


def test_list_edges_data_with_name_filter(mock_env: None) -> None:
    """Test list_edges_data filters by name substring."""
    from orcheo.edges.registry import EdgeMetadata, edge_registry

    test_meta = EdgeMetadata(
        name="SpecialEdge",
        description="Special edge for testing",
        category="test",
    )
    edge_registry._edges["SpecialEdge"] = lambda: None
    edge_registry._metadata["SpecialEdge"] = test_meta

    try:
        result = list_edges_data(category="special")
        assert isinstance(result, list)
        # Should find the edge by name
        names = [edge["name"] for edge in result]
        assert "SpecialEdge" in names
    finally:
        edge_registry._edges.pop("SpecialEdge", None)
        edge_registry._metadata.pop("SpecialEdge", None)


def test_show_edge_data_returns_metadata(mock_env: None) -> None:
    """Test show_edge_data returns edge metadata."""
    from pydantic import BaseModel
    from orcheo.edges.registry import EdgeMetadata, edge_registry

    class TestEdge(BaseModel):
        """Test edge with schema."""

        test_field: str
        count: int

    test_meta = EdgeMetadata(
        name="TestEdgeWithSchema",
        description="Test edge",
        category="test",
    )
    edge_registry._edges["TestEdgeWithSchema"] = TestEdge
    edge_registry._metadata["TestEdgeWithSchema"] = test_meta

    try:
        result = show_edge_data("TestEdgeWithSchema")
        assert result["name"] == "TestEdgeWithSchema"
        assert result["category"] == "test"
        assert result["description"] == "Test edge"
        assert "schema" in result
    finally:
        edge_registry._edges.pop("TestEdgeWithSchema", None)
        edge_registry._metadata.pop("TestEdgeWithSchema", None)


def test_show_edge_data_with_attributes_only(mock_env: None) -> None:
    """Test show_edge_data with edge that has attributes but no model_json_schema."""
    from orcheo.edges.registry import EdgeMetadata, edge_registry

    class TestEdgeWithAttrs:
        """Edge with annotations but no model_json_schema."""

        test_attr: str
        count: int

    test_meta = EdgeMetadata(
        name="TestEdgeWithAttrs",
        description="Test edge with attributes",
        category="test",
    )
    edge_registry._edges["TestEdgeWithAttrs"] = TestEdgeWithAttrs
    edge_registry._metadata["TestEdgeWithAttrs"] = test_meta

    try:
        result = show_edge_data("TestEdgeWithAttrs")
        assert result["name"] == "TestEdgeWithAttrs"
        assert "attributes" in result
        assert "test_attr" in result["attributes"]
        assert "count" in result["attributes"]
    finally:
        edge_registry._edges.pop("TestEdgeWithAttrs", None)
        edge_registry._metadata.pop("TestEdgeWithAttrs", None)


def test_show_edge_data_not_found(mock_env: None) -> None:
    """Test show_edge_data raises CLIError for non-existent edge."""
    with pytest.raises(CLIError, match="Edge 'NonExistentEdge' is not registered"):
        show_edge_data("NonExistentEdge")


def test_show_edge_data_missing_metadata(mock_env: None) -> None:
    """Test show_edge_data raises CLIError when metadata is missing."""
    from orcheo.edges.registry import edge_registry

    # Register edge without metadata
    edge_registry._edges["EdgeNoMeta"] = lambda: None

    try:
        with pytest.raises(CLIError, match="Edge 'EdgeNoMeta' is not registered"):
            show_edge_data("EdgeNoMeta")
    finally:
        edge_registry._edges.pop("EdgeNoMeta", None)


def test_show_edge_data_missing_edge_class(mock_env: None) -> None:
    """Test show_edge_data raises CLIError when edge class is missing."""
    from orcheo.edges.registry import EdgeMetadata, edge_registry

    test_meta = EdgeMetadata(
        name="EdgeNoClass",
        description="Edge without class",
        category="test",
    )
    edge_registry._metadata["EdgeNoClass"] = test_meta

    try:
        with pytest.raises(CLIError, match="Edge 'EdgeNoClass' is not registered"):
            show_edge_data("EdgeNoClass")
    finally:
        edge_registry._metadata.pop("EdgeNoClass", None)
