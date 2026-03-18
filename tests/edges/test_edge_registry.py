"""Tests for the edge registry module."""

from typing import Any
import pytest
from orcheo.edges.registry import EdgeMetadata, EdgeRegistry


def test_get_metadata_by_callable_exact_match() -> None:
    """get_metadata_by_callable returns metadata for exact callable match."""
    registry = EdgeRegistry()

    def my_edge(state: Any) -> Any:
        return state

    metadata = EdgeMetadata(
        name="my_edge",
        description="A test edge",
        category="test",
    )

    registry.register(metadata)(my_edge)

    result = registry.get_metadata_by_callable(my_edge)
    assert result is not None
    assert result.name == "my_edge"
    assert result.description == "A test edge"
    assert result.category == "test"


def test_get_metadata_by_callable_instance_match() -> None:
    """get_metadata_by_callable returns metadata for instance of registered class."""
    registry = EdgeRegistry()

    class MyEdge:
        def __call__(self, state: Any) -> Any:
            return state

    metadata = EdgeMetadata(
        name="class_edge",
        description="A class-based edge",
        category="classes",
    )

    registry.register(metadata)(MyEdge)

    instance = MyEdge()
    result = registry.get_metadata_by_callable(instance)
    assert result is not None
    assert result.name == "class_edge"
    assert result.description == "A class-based edge"


def test_get_metadata_by_callable_no_match() -> None:
    """get_metadata_by_callable returns None for unregistered callable."""
    registry = EdgeRegistry()

    def unregistered_edge(state: Any) -> Any:
        return state

    result = registry.get_metadata_by_callable(unregistered_edge)
    assert result is None


def test_get_metadata_by_callable_not_instance() -> None:
    """get_metadata_by_callable returns None when callable is not an instance."""
    registry = EdgeRegistry()

    class RegisteredEdge:
        pass

    class DifferentEdge:
        def __call__(self) -> None:
            pass

    metadata = EdgeMetadata(
        name="registered",
        description="Registered edge",
        category="test",
    )

    registry.register(metadata)(RegisteredEdge)

    # Different class instance should not match
    different_instance = DifferentEdge()
    result = registry.get_metadata_by_callable(different_instance)
    assert result is None


def test_get_metadata_returns_registered_entry() -> None:
    """get_metadata surfaces registered metadata by edge name."""
    registry = EdgeRegistry()
    metadata = EdgeMetadata(name="alpha", description="Alpha edge", category="demo")
    registry.register(metadata)(lambda _: None)

    assert registry.get_metadata("alpha") is metadata
    assert registry.get_metadata("missing") is None


def test_list_metadata_returns_sorted_entries() -> None:
    """list_metadata returns metadata sorted by case-insensitive name."""
    registry = EdgeRegistry()
    first = EdgeMetadata(name="Beta", description="", category="")
    second = EdgeMetadata(name="alpha", description="", category="")
    registry.register(first)(lambda _: None)
    registry.register(second)(lambda _: None)

    names = [item.name for item in registry.list_metadata()]
    assert names == ["alpha", "Beta"]


def test_alias_lookup_resolves_to_canonical_metadata() -> None:
    """Aliases resolve edge implementations and do not appear in discovery."""
    registry = EdgeRegistry()
    metadata = EdgeMetadata(name="IfElseEdge", description="Decision edge")

    class IfElseEdge:
        pass

    registry.register(metadata)(IfElseEdge)
    registry.register_alias("IfElse", "IfElseEdge")

    assert registry.get_edge("IfElse") is IfElseEdge
    assert registry.get_metadata("IfElse") is metadata
    assert [item.name for item in registry.list_metadata()] == ["IfElseEdge"]
    assert registry.get_aliases("IfElseEdge") == ["IfElse"]


def test_register_rejects_name_colliding_with_alias() -> None:
    """Canonical registrations cannot reuse reserved legacy aliases."""
    registry = EdgeRegistry()
    registry.register(EdgeMetadata(name="IfElseEdge", description="Decision"))(
        lambda state: state
    )
    registry.register_alias("IfElse", "IfElseEdge")

    with pytest.raises(ValueError, match="IfElse"):
        registry.register(EdgeMetadata(name="IfElse", description="Legacy"))(
            lambda state: state
        )


def test_edge_metadata_default_category() -> None:
    """EdgeMetadata defaults category to 'logic'."""
    metadata = EdgeMetadata(
        name="test_edge",
        description="Test edge without explicit category",
    )
    assert metadata.category == "logic"


def test_edge_metadata_custom_category() -> None:
    """EdgeMetadata accepts custom category."""
    metadata = EdgeMetadata(
        name="test_edge",
        description="Test edge with custom category",
        category="custom",
    )
    assert metadata.category == "custom"


def test_register_alias_for_unknown_canonical_raises() -> None:
    """register_alias raises ValueError when canonical edge does not exist."""
    registry = EdgeRegistry()
    with pytest.raises(ValueError, match="unknown_edge"):
        registry.register_alias("alias", "unknown_edge")


def test_register_alias_when_alias_equals_canonical_is_noop() -> None:
    """register_alias is a no-op when alias equals the canonical name (line 72)."""
    registry = EdgeRegistry()
    metadata = EdgeMetadata(name="MyEdge", description="")
    registry.register(metadata)(lambda s: s)
    # Registering alias same as canonical should not raise or add anything
    registry.register_alias("MyEdge", "MyEdge")
    # No duplicate alias should exist
    assert registry.get_aliases("MyEdge") == []


def test_get_aliases_for_unknown_name_returns_empty() -> None:
    """get_aliases returns [] when the edge is not registered (line 105)."""
    registry = EdgeRegistry()
    assert registry.get_aliases("does_not_exist") == []


def test_unregister_unknown_is_noop() -> None:
    """unregister silently returns when name is not found (line 126)."""
    registry = EdgeRegistry()
    registry.unregister("not_there")  # should not raise


def test_unregister_removes_associated_aliases() -> None:
    """unregister removes the edge and all its aliases (line 135)."""
    registry = EdgeRegistry()
    metadata = EdgeMetadata(name="TargetEdge", description="")
    registry.register(metadata)(lambda s: s)
    registry.register_alias("OldEdge", "TargetEdge")
    registry.register_alias("LegacyEdge", "TargetEdge")

    registry.unregister("TargetEdge")

    assert registry.get_edge("TargetEdge") is None
    assert registry.get_edge("OldEdge") is None
    assert registry.get_edge("LegacyEdge") is None
