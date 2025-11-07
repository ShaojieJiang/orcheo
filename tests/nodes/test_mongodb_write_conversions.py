"""MongoDBNode conversion tests for write operations."""

from __future__ import annotations
from typing import TYPE_CHECKING
from unittest.mock import Mock
from pymongo.results import (
    BulkWriteResult,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)


if TYPE_CHECKING:
    from tests.nodes.conftest import MongoTestContext


def test_convert_insert_result_to_dict(mongo_context: MongoTestContext) -> None:
    """InsertOneResult should convert with the inserted identifier."""

    node = mongo_context.build_node(operation="insert_one")
    mock_result = Mock(spec=InsertOneResult)
    mock_result.inserted_id = "507f1f77bcf86cd799439011"
    mock_result.acknowledged = True

    result = node._convert_result_to_dict(mock_result)
    assert isinstance(result, dict)
    assert result["operation"] == "insert_one"
    assert result["inserted_id"] == "507f1f77bcf86cd799439011"
    assert result["acknowledged"] is True


def test_convert_insert_many_result_to_dict(mongo_context: MongoTestContext) -> None:
    """InsertManyResult should convert with the inserted identifiers."""

    node = mongo_context.build_node(operation="insert_many")
    mock_result = Mock(spec=InsertManyResult)
    mock_result.inserted_ids = [
        "507f1f77bcf86cd799439011",
        "507f1f77bcf86cd799439012",
    ]
    mock_result.acknowledged = True

    result = node._convert_result_to_dict(mock_result)
    assert isinstance(result, dict)
    assert result["operation"] == "insert_many"
    assert result["inserted_ids"] == [
        "507f1f77bcf86cd799439011",
        "507f1f77bcf86cd799439012",
    ]
    assert result["acknowledged"] is True


def test_convert_update_result_to_dict(mongo_context: MongoTestContext) -> None:
    """UpdateResult should expose counts and the upsert identifier."""

    node = mongo_context.build_node(operation="update_one")
    mock_result = Mock(spec=UpdateResult)
    mock_result.matched_count = 1
    mock_result.modified_count = 1
    mock_result.upserted_id = None
    mock_result.acknowledged = True

    result = node._convert_result_to_dict(mock_result)
    assert isinstance(result, dict)
    assert result["operation"] == "update"
    assert result["matched_count"] == 1
    assert result["modified_count"] == 1
    assert result["upserted_id"] is None
    assert result["acknowledged"] is True


def test_convert_delete_result_to_dict(mongo_context: MongoTestContext) -> None:
    """DeleteResult should surface deleted counts."""

    node = mongo_context.build_node(operation="delete_one")
    mock_result = Mock(spec=DeleteResult)
    mock_result.deleted_count = 1
    mock_result.acknowledged = True

    result = node._convert_result_to_dict(mock_result)
    assert isinstance(result, dict)
    assert result["operation"] == "delete"
    assert result["deleted_count"] == 1
    assert result["acknowledged"] is True


def test_convert_bulk_write_result_to_dict(mongo_context: MongoTestContext) -> None:
    """BulkWriteResult should expose all counters and upsert details."""

    node = mongo_context.build_node(operation="bulk_write")
    mock_result = Mock(spec=BulkWriteResult)
    mock_result.inserted_count = 2
    mock_result.matched_count = 3
    mock_result.modified_count = 3
    mock_result.deleted_count = 1
    mock_result.upserted_count = 1
    mock_result.upserted_ids = {0: "507f1f77bcf86cd799439011"}
    mock_result.acknowledged = True

    result = node._convert_result_to_dict(mock_result)
    assert isinstance(result, dict)
    assert result["operation"] == "bulk_write"
    assert result["inserted_count"] == 2
    assert result["matched_count"] == 3
    assert result["modified_count"] == 3
    assert result["deleted_count"] == 1
    assert result["upserted_count"] == 1
    assert result["upserted_ids"] == {"0": "507f1f77bcf86cd799439011"}
    assert result["acknowledged"] is True


def test_convert_bulk_write_result_no_upserted_ids(
    mongo_context: MongoTestContext,
) -> None:
    """BulkWriteResult should handle missing upserted identifiers."""

    node = mongo_context.build_node(operation="bulk_write")
    mock_result = Mock(spec=BulkWriteResult)
    mock_result.inserted_count = 2
    mock_result.matched_count = 3
    mock_result.modified_count = 3
    mock_result.deleted_count = 1
    mock_result.upserted_count = 0
    mock_result.upserted_ids = None
    mock_result.acknowledged = True

    result = node._convert_result_to_dict(mock_result)
    assert isinstance(result, dict)
    assert result["upserted_ids"] == {}
