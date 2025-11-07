"""Cursor-focused MongoDBNode conversion tests."""

from __future__ import annotations
from typing import TYPE_CHECKING
from unittest.mock import Mock
from pymongo.command_cursor import CommandCursor
from pymongo.cursor import Cursor


if TYPE_CHECKING:
    from tests.nodes.conftest import MongoTestContext


def test_convert_cursor_to_list_dict(mongo_context: MongoTestContext) -> None:
    """Cursor results should convert into list[dict]."""

    node = mongo_context.build_node(operation="find")
    mock_cursor = Mock(spec=Cursor)
    mock_cursor.__iter__ = Mock(
        return_value=iter(
            [
                {"_id": "1", "name": "doc1"},
                {"_id": "2", "name": "doc2"},
            ]
        )
    )

    result = node._convert_result_to_dict(mock_cursor)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == {"_id": "1", "name": "doc1"}
    assert result[1] == {"_id": "2", "name": "doc2"}


def test_convert_command_cursor_to_list_dict(mongo_context: MongoTestContext) -> None:
    """CommandCursor results should convert into list[dict]."""

    node = mongo_context.build_node(operation="aggregate")
    mock_cursor = Mock(spec=CommandCursor)
    mock_cursor.__iter__ = Mock(
        return_value=iter(
            [
                {"_id": "1", "count": 5},
                {"_id": "2", "count": 3},
            ]
        )
    )

    result = node._convert_result_to_dict(mock_cursor)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == {"_id": "1", "count": 5}
    assert result[1] == {"_id": "2", "count": 3}


def test_convert_list_to_list_dict(mongo_context: MongoTestContext) -> None:
    """Lists of primitives or dicts should normalize properly."""

    node = mongo_context.build_node(operation="distinct")

    primitive_result = node._convert_result_to_dict(["value1", "value2", "value3"])
    assert isinstance(primitive_result, list)
    assert primitive_result == [
        {"value": "value1"},
        {"value": "value2"},
        {"value": "value3"},
    ]

    dict_result = node._convert_result_to_dict([{"key1": "val1"}, {"key2": "val2"}])
    assert isinstance(dict_result, list)
    assert dict_result == [{"key1": "val1"}, {"key2": "val2"}]


def test_convert_object_with_dict_to_dict(mongo_context: MongoTestContext) -> None:
    """Objects exposing __dict__ should convert to dictionaries."""

    node = mongo_context.build_node(operation="find")

    class CustomObject:
        def __init__(self) -> None:
            self.attr1 = "value1"
            self.attr2 = 42

    result = node._convert_result_to_dict(CustomObject())
    assert isinstance(result, dict)
    assert result["attr1"] == "value1"
    assert result["attr2"] == 42


def test_convert_unknown_object_to_dict(mongo_context: MongoTestContext) -> None:
    """Fallback to string conversion for unknown objects."""

    node = mongo_context.build_node(operation="find")

    class ComplexObject:
        __slots__ = ()

        def __str__(self) -> str:
            return "complex_object_representation"

    result = node._convert_result_to_dict(ComplexObject())
    assert isinstance(result, dict)
    assert result["result"] == "complex_object_representation"
