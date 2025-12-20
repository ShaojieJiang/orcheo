"""MongoDB node."""

from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import Field, PrivateAttr
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.command_cursor import CommandCursor
from pymongo.cursor import Cursor
from pymongo.results import (
    BulkWriteResult,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="MongoDBNode",
        description="MongoDB node",
        category="mongodb",
    )
)
class MongoDBNode(TaskNode):
    """MongoDB node.

    To use this node, you need to set the following environment variables:
    - MDB_CONNECTION_STRING: Required.
    """

    connection_string: str = "[[mdb_connection_string]]"
    """Connection string for MongoDB."""
    database: str
    """The database to use."""
    collection: str
    """The collection to use."""
    operation: Literal[
        "find",
        "find_one",
        "find_raw_batches",
        "insert_one",
        "insert_many",
        "update_one",
        "update_many",
        "replace_one",
        "delete_one",
        "delete_many",
        "aggregate",
        "aggregate_raw_batches",
        "count_documents",
        "estimated_document_count",
        "distinct",
        "find_one_and_delete",
        "find_one_and_replace",
        "find_one_and_update",
        "bulk_write",
        "create_index",
        "create_indexes",
        "drop_index",
        "drop_indexes",
        "list_indexes",
        "index_information",
        "create_search_index",
        "create_search_indexes",
        "drop_search_index",
        "update_search_index",
        "list_search_indexes",
        "drop",
        "rename",
        "options",
        "watch",
    ]
    query: dict | list[dict[str, Any]] = Field(default_factory=dict)
    """Legacy query payload passed directly to the operation."""
    filter: dict[str, Any] | None = Field(
        default=None, description="Filter document for query/update operations"
    )
    update: dict[str, Any] | None = Field(
        default=None, description="Update document for update operations"
    )
    pipeline: list[dict[str, Any]] | None = Field(
        default=None, description="Aggregation pipeline for aggregate operations"
    )
    sort: dict[str, int] | list[tuple[str, int]] | None = Field(
        default=None, description="Sort specification for find operations"
    )
    limit: int | None = Field(
        default=None, ge=0, description="Limit for find operations"
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional pymongo options passed to the operation",
    )
    _client: MongoClient | None = PrivateAttr(default=None)
    _collection: Collection | None = PrivateAttr(default=None)

    def _resolve_filter(self) -> dict[str, Any]:
        """Resolve a filter document from structured or legacy inputs."""
        if self.filter is not None:
            return dict(self.filter)
        if isinstance(self.query, dict):
            return dict(self.query)
        return {}

    def _resolve_update(self) -> dict[str, Any]:
        """Resolve an update/replacement document from inputs."""
        if self.update is not None:
            return dict(self.update)
        if isinstance(self.query, dict):
            candidate = self.query.get("update")
            if isinstance(candidate, dict):
                return dict(candidate)
        msg = "update is required for update operations"
        raise ValueError(msg)

    def _resolve_pipeline(self) -> list[dict[str, Any]]:
        """Resolve an aggregation pipeline from inputs."""
        if self.pipeline is not None:
            return list(self.pipeline)
        if isinstance(self.query, list):
            return list(self.query)
        if isinstance(self.query, dict):
            candidate = self.query.get("pipeline")
            if isinstance(candidate, list):
                return list(candidate)
        msg = "pipeline is required for aggregate operations"
        raise ValueError(msg)

    def _normalize_sort(
        self, value: dict[str, int] | list[tuple[str, int]]
    ) -> list[tuple[str, int]]:
        """Normalize sort specifications into list-of-tuples."""
        if isinstance(value, dict):
            return list(value.items())
        return list(value)

    def _build_operation_call(self) -> tuple[list[Any], dict[str, Any]]:
        """Return positional args and kwargs for the configured operation."""
        filter_operations = {
            "find",
            "find_one",
            "find_raw_batches",
            "count_documents",
            "delete_one",
            "delete_many",
            "find_one_and_delete",
        }
        find_operations = {"find", "find_one", "find_raw_batches"}
        update_operations = {
            "update_one",
            "update_many",
            "find_one_and_update",
            "replace_one",
            "find_one_and_replace",
        }
        pipeline_operations = {"aggregate", "aggregate_raw_batches"}

        if self.operation in pipeline_operations:
            pipeline = self._resolve_pipeline()
            return [pipeline], dict(self.options)

        if self.operation in update_operations:
            filter_doc = self._resolve_filter()
            update_doc = self._resolve_update()
            return [filter_doc, update_doc], dict(self.options)

        if self.operation in filter_operations:
            filter_doc = self._resolve_filter()
            kwargs = dict(self.options)
            if self.operation in find_operations:
                if self.sort is not None:
                    kwargs["sort"] = self._normalize_sort(self.sort)
                if self.limit is not None:
                    kwargs["limit"] = self.limit
            return [filter_doc], kwargs

        return [self.query], dict(self.options)

    def _ensure_collection(self) -> None:
        """Ensure the MongoDB collection is initialised."""
        if self._client is None:
            self._client = MongoClient(self.connection_string)
        if self._collection is None:
            self._collection = self._client[self.database][self.collection]

    def _convert_result_to_dict(self, result: Any) -> dict | list[dict]:
        """Convert MongoDB operation result to dict or list[dict] format."""
        converted_result: dict | list[dict]

        match result:
            case Cursor() | CommandCursor():
                converted_result = [dict(doc) for doc in result]

            case None | int() | float() | str() | bool():
                converted_result = {"result": result}

            case list():
                converted_result = [
                    {"value": item} if not isinstance(item, dict) else dict(item)
                    for item in result
                ]

            case InsertOneResult():
                converted_result = {
                    "operation": "insert_one",
                    "inserted_id": str(result.inserted_id),
                    "acknowledged": result.acknowledged,
                }

            case InsertManyResult():
                converted_result = {
                    "operation": "insert_many",
                    "inserted_ids": [str(id_) for id_ in result.inserted_ids],
                    "acknowledged": result.acknowledged,
                }

            case UpdateResult():
                converted_result = {
                    "operation": "update",
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count,
                    "upserted_id": str(result.upserted_id)
                    if result.upserted_id
                    else None,
                    "acknowledged": result.acknowledged,
                }

            case DeleteResult():
                converted_result = {
                    "operation": "delete",
                    "deleted_count": result.deleted_count,
                    "acknowledged": result.acknowledged,
                }

            case BulkWriteResult():
                converted_result = {
                    "operation": "bulk_write",
                    "inserted_count": result.inserted_count,
                    "matched_count": result.matched_count,
                    "modified_count": result.modified_count,
                    "deleted_count": result.deleted_count,
                    "upserted_count": result.upserted_count,
                    "upserted_ids": {
                        str(k): str(v) for k, v in (result.upserted_ids or {}).items()
                    },
                    "acknowledged": result.acknowledged,
                }

            case _ if hasattr(result, "__dict__"):
                converted_result = dict(result.__dict__)

            case _:
                converted_result = {"result": str(result)}

        return converted_result

    async def run(self, state: State, config: RunnableConfig) -> dict:
        """Run the MongoDB node with persistent session."""
        self._ensure_collection()
        assert self._collection is not None
        operation = getattr(self._collection, self.operation)
        args, kwargs = self._build_operation_call()
        result = operation(*args, **kwargs)
        return {"data": self._convert_result_to_dict(result)}

    def __del__(self) -> None:
        """Automatic cleanup when object is garbage collected."""
        if self._client is not None:
            self._client.close()


@registry.register(
    NodeMetadata(
        name="MongoDBAggregateNode",
        description="MongoDB aggregate wrapper",
        category="mongodb",
    )
)
class MongoDBAggregateNode(MongoDBNode):
    """MongoDB aggregate wrapper with a required pipeline."""

    operation: Literal["aggregate"] = "aggregate"
    pipeline: list[dict[str, Any]]


@registry.register(
    NodeMetadata(
        name="MongoDBFindNode",
        description="MongoDB find wrapper with sort and limit support",
        category="mongodb",
    )
)
class MongoDBFindNode(MongoDBNode):
    """MongoDB find wrapper with filter, sort, and limit fields."""

    operation: Literal["find"] = "find"
    filter: dict[str, Any] = Field(default_factory=dict)


@registry.register(
    NodeMetadata(
        name="MongoDBUpdateManyNode",
        description="MongoDB update_many wrapper",
        category="mongodb",
    )
)
class MongoDBUpdateManyNode(MongoDBNode):
    """MongoDB update_many wrapper with filter and update documents."""

    operation: Literal["update_many"] = "update_many"
    filter: dict[str, Any]
    update: dict[str, Any]


__all__ = [
    "MongoDBAggregateNode",
    "MongoDBFindNode",
    "MongoDBNode",
    "MongoDBUpdateManyNode",
]
