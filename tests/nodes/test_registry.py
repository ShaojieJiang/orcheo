"""Tests for the node registry module."""

from orcheo.nodes.registry import NodeMetadata, NodeRegistry


def test_get_metadata_by_callable_exact_match() -> None:
    """get_metadata_by_callable returns metadata for exact callable match."""

    registry = NodeRegistry()

    def my_node(state):
        return state

    metadata = NodeMetadata(
        name="my_node",
        description="A test node",
        category="test",
    )

    registry.register(metadata)(my_node)

    result = registry.get_metadata_by_callable(my_node)
    assert result is not None
    assert result.name == "my_node"
    assert result.description == "A test node"
    assert result.category == "test"


def test_get_metadata_by_callable_instance_match() -> None:
    """get_metadata_by_callable returns metadata for instance of registered class."""

    registry = NodeRegistry()

    class MyNode:
        def __call__(self, state):
            return state

    metadata = NodeMetadata(
        name="class_node",
        description="A class-based node",
        category="classes",
    )

    registry.register(metadata)(MyNode)

    instance = MyNode()
    result = registry.get_metadata_by_callable(instance)
    assert result is not None
    assert result.name == "class_node"
    assert result.description == "A class-based node"


def test_get_metadata_by_callable_no_match() -> None:
    """get_metadata_by_callable returns None for unregistered callable."""

    registry = NodeRegistry()

    def unregistered_node(state):
        return state

    result = registry.get_metadata_by_callable(unregistered_node)
    assert result is None
