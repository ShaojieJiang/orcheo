"""Additional MongoDBNode helper and error-handling tests."""

from __future__ import annotations
from typing import Any
from unittest.mock import MagicMock, patch
import pytest
from bson import ObjectId
from langchain_core.runnables import RunnableConfig
from pymongo.errors import (
    AutoReconnect,
    ConfigurationError,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)
from orcheo.graph.state import State
from orcheo.nodes.mongodb import MongoDBNode, MongoDBUpdateManyNode


def _build_node(*, operation: str, **overrides: Any) -> MongoDBNode:
    """Create a MongoDBNode with sensible defaults for helper tests."""

    base_kwargs = {
        "name": "helper_node",
        "connection_string": "mongodb://helper",
        "database": "test_db",
        "collection": "test_collection",
        "operation": operation,
    }
    base_kwargs.update(overrides)
    return MongoDBNode(**base_kwargs)


def _build_update_many() -> MongoDBUpdateManyNode:
    """Create a MongoDBUpdateManyNode with sane defaults."""

    return MongoDBUpdateManyNode(
        name="update_many",
        database="test_db",
        collection="test_collection",
        filter={"match": True},
        update={"$set": {"match": True}},
    )


def test_limit_validator_accepts_templates_and_numbers() -> None:
    assert MongoDBNode._validate_limit(None) is None
    assert MongoDBNode._validate_limit("{{limit}}") == "{{limit}}"
    assert MongoDBNode._validate_limit("10") == 10


def test_limit_validator_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="limit must be an integer"):
        MongoDBNode._validate_limit("bad")
    with pytest.raises(ValueError, match="limit must be >= 0"):
        MongoDBNode._validate_limit(-1)


def test_resolve_filter_prefers_filter_and_falls_back_to_empty() -> None:
    node = _build_node(operation="find", filter={"status": "ok"})
    assert node._resolve_filter() == {"status": "ok"}

    node.filter = None
    node.query = {"status": "fallback"}
    assert node._resolve_filter() == {"status": "fallback"}

    node.query = [{"status": "list"}]
    assert node._resolve_filter() == {}


def test_resolve_update_handles_explicit_and_query_updates() -> None:
    node = _build_node(operation="update_one", update={"$set": {"count": 1}})
    assert node._resolve_update() == {"$set": {"count": 1}}

    node.update = None
    node.query = {"update": {"$set": {"count": 2}}}
    assert node._resolve_update() == {"$set": {"count": 2}}

    node.query = {"other": "value"}
    with pytest.raises(ValueError, match="update is required for update operations"):
        node._resolve_update()


def test_resolve_pipeline_handles_variants_and_errors() -> None:
    node = _build_node(
        operation="aggregate",
        pipeline=[{"$match": {"value": 1}}],
    )
    assert node._resolve_pipeline() == [{"$match": {"value": 1}}]

    node.pipeline = None
    node.query = [{"$match": {"value": 2}}]
    assert node._resolve_pipeline() == [{"$match": {"value": 2}}]

    node.query = {"pipeline": [{"$match": {"value": 3}}]}
    assert node._resolve_pipeline() == [{"$match": {"value": 3}}]

    node.query = {"foo": "bar"}
    with pytest.raises(
        ValueError, match="pipeline is required for aggregate operations"
    ):
        node._resolve_pipeline()


def test_resolve_update_uses_query_candidate_when_update_missing() -> None:
    node = _build_node(
        operation="update_one",
        query={"update": {"$set": {"count": 5}}},
    )
    node.update = None

    assert node._resolve_update() == {"$set": {"count": 5}}


def test_resolve_pipeline_uses_query_candidate_when_missing() -> None:
    node = _build_node(
        operation="aggregate",
        query={"pipeline": [{"$match": {"state": "active"}}]},
    )
    node.pipeline = None

    assert node._resolve_pipeline() == [{"$match": {"state": "active"}}]


def test_normalize_sort_converts_dicts_and_lists() -> None:
    node = _build_node(operation="find")
    assert node._normalize_sort({"name": -1}) == [("name", -1)]
    assert node._normalize_sort([("name", -1)]) == [("name", -1)]


def test_build_operation_call_covers_each_operation_type() -> None:
    object_id = ObjectId("507f1f77bcf86cd799439011")

    aggregate_node = _build_node(
        operation="aggregate",
        pipeline=[{"$match": {"_id": str(object_id)}}],
    )
    aggregate_args, aggregate_kwargs = aggregate_node._build_operation_call()
    assert aggregate_kwargs == {}
    assert aggregate_args[0][0]["$match"]["_id"] == object_id

    update_node = _build_node(
        operation="update_one",
        filter={"_id": str(object_id)},
        update={"$set": {"value": 1}},
    )
    update_args, update_kwargs = update_node._build_operation_call()
    assert update_kwargs == {}
    assert update_args[0]["_id"] == object_id
    assert update_args[1] == {"$set": {"value": 1}}

    find_node = _build_node(
        operation="find",
        filter={"status": "active"},
        sort={"isoDate": -1},
        limit=5,
    )
    find_args, find_kwargs = find_node._build_operation_call()
    assert find_kwargs["sort"] == [("isoDate", -1)]
    assert find_kwargs["limit"] == 5
    assert find_args[0] == {"status": "active"}

    other_node = _build_node(operation="create_index", query={"name": 1})
    other_args, other_kwargs = other_node._build_operation_call()
    assert other_args == [{"name": 1}]
    assert other_kwargs == {}


def test_resolve_limit_requires_integer_values() -> None:
    node = _build_node(operation="find", limit="{{limit}}")
    with pytest.raises(
        ValueError, match="limit must resolve to an integer before execution"
    ):
        node._resolve_limit()

    node.limit = "bad"
    with pytest.raises(ValueError, match="limit must be an integer"):
        node._resolve_limit()

    node.limit = None
    with pytest.raises(ValueError, match="limit is not set for find operations"):
        node._resolve_limit()


def test_coerce_object_ids_converts_nested_ids() -> None:
    object_id = ObjectId("507f1f77bcf86cd799439011")
    payload = {
        "_id": str(object_id),
        "nested": [{"_id": str(object_id)}],
        "other": {"_id": "not-an-id"},
    }

    coerced = MongoDBNode._coerce_object_ids(payload)
    assert coerced["_id"] == object_id
    assert coerced["nested"][0]["_id"] == object_id
    assert coerced["other"]["_id"] == "not-an-id"


def test_shared_client_lifecycle() -> None:
    MongoDBNode._client_cache.clear()
    MongoDBNode._client_ref_counts.clear()
    client_mock = MagicMock()

    with patch("orcheo.nodes.mongodb.MongoClient", return_value=client_mock):
        first = MongoDBNode._get_shared_client("conn")
        second = MongoDBNode._get_shared_client("conn")
        assert first is client_mock
        assert second is client_mock
        assert MongoDBNode._client_ref_counts["conn"] == 2

    MongoDBNode._release_shared_client("conn")
    assert MongoDBNode._client_ref_counts["conn"] == 1
    client_mock.close.assert_not_called()

    MongoDBNode._release_shared_client("conn")
    assert "conn" not in MongoDBNode._client_ref_counts
    client_mock.close.assert_called_once()

    client_one = MagicMock()
    client_two = MagicMock()
    MongoDBNode._client_cache.clear()
    MongoDBNode._client_ref_counts.clear()

    with patch(
        "orcheo.nodes.mongodb.MongoClient", side_effect=[client_one, client_two]
    ):
        MongoDBNode._get_shared_client("conn-one")
        MongoDBNode._get_shared_client("conn-two")

    MongoDBNode._close_all_clients()
    client_one.close.assert_called_once()
    client_two.close.assert_called_once()


def test_release_shared_client_ignores_unknown_connection() -> None:
    MongoDBNode._client_cache.clear()
    MongoDBNode._client_ref_counts.clear()

    MongoDBNode._release_shared_client("missing")
    assert MongoDBNode._client_cache == {}
    assert MongoDBNode._client_ref_counts == {}


def test_ensure_collection_raises_when_client_missing() -> None:
    node = _build_node(operation="find")
    with patch.object(MongoDBNode, "_get_shared_client", return_value=None):
        with pytest.raises(
            RuntimeError, match="MongoDB client could not be initialized"
        ):
            node._ensure_collection()


def test_ensure_collection_switches_clients_on_connection_change() -> None:
    node = _build_node(operation="find")
    node._client = MagicMock()
    node._client_key = "old-connection"
    node.connection_string = "new-connection"

    replacement_db = MagicMock()
    replacement_collection = MagicMock()
    replacement_db.__getitem__.return_value = replacement_collection

    replacement_client = MagicMock()
    replacement_client.__getitem__.return_value = replacement_db

    with patch.object(
        MongoDBNode, "_get_shared_client", return_value=replacement_client
    ) as get_client:
        with patch.object(MongoDBNode, "_release_client") as release_client:
            node._ensure_collection()

    release_client.assert_called_once()
    get_client.assert_called_once_with("new-connection")
    assert node._client is replacement_client
    assert node._client_key == "new-connection"
    assert node._collection is replacement_collection


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception, message",
    [
        (AutoReconnect("test"), "MongoDB network error"),
        (OperationFailure("auth", 13), "MongoDB authentication/authorization error"),
        (OperationFailure("other", 1), "MongoDB operation error"),
        (ConfigurationError("bad"), "MongoDB configuration error"),
        (PyMongoError("generic"), "MongoDB error during"),
        (
            ServerSelectionTimeoutError("timeout"),
            "MongoDB network error",
        ),
    ],
)
async def test_run_translates_pymongo_errors(
    mongo_context,
    exception,
    message,
) -> None:
    node = mongo_context.build_node(operation="find")
    state = State(messages=[], inputs={}, results={})

    mongo_context.collection.find.side_effect = exception

    with pytest.raises(RuntimeError, match=message):
        await node.run(state, RunnableConfig())


def test_update_many_requires_filter_and_update() -> None:
    node = _build_update_many()
    node.filter = None
    with pytest.raises(
        ValueError, match="filter is required for update_many operations"
    ):
        node._resolve_filter()

    node = _build_update_many()
    node.update = None
    with pytest.raises(
        ValueError, match="update is required for update_many operations"
    ):
        node._resolve_update()

    node = _build_update_many()
    node.update = {}
    with pytest.raises(
        ValueError, match="update must not be empty for update_many operations"
    ):
        node._resolve_update()
