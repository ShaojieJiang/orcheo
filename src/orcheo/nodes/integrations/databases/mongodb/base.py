"""MongoDB nodes and shared client management."""

from __future__ import annotations
import atexit
from collections.abc import Callable
from threading import Lock
from typing import Any, ClassVar, Literal
from bson import ObjectId
from langchain_core.runnables import RunnableConfig
from pydantic import Field, PrivateAttr, field_validator
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.command_cursor import CommandCursor
from pymongo.cursor import Cursor
from pymongo.errors import (
    AutoReconnect,
    ConfigurationError,
    ConnectionFailure,
    NetworkTimeout,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)
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


class MongoDBClientNode(TaskNode):
    """Base node with shared MongoDB client handling."""

    connection_string: str = "[[mdb_connection_string]]"
    """Connection string for MongoDB."""
    database: str
    """The database to use."""
    collection: str
    """The collection to use."""

    _client_cache: ClassVar[dict[str, MongoClient]] = {}
    _client_ref_counts: ClassVar[dict[str, int]] = {}
    _client_lock: ClassVar[Lock] = Lock()
    _client: MongoClient | None = PrivateAttr(default=None)
    _collection: Collection | None = PrivateAttr(default=None)
    _client_key: str | None = PrivateAttr(default=None)

    @classmethod
    def _encode_bson(cls, value: Any) -> Any:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, dict):
            return {key: cls._encode_bson(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._encode_bson(item) for item in value]
        return value

    @classmethod
    def _get_shared_client(cls, connection_string: str) -> MongoClient:
        with cls._client_lock:
            client = cls._client_cache.get(connection_string)
            if client is None:
                client = MongoClient(connection_string)
                cls._client_cache[connection_string] = client
                cls._client_ref_counts[connection_string] = 0
            cls._client_ref_counts[connection_string] = (
                cls._client_ref_counts.get(connection_string, 0) + 1
            )
        return client

    @classmethod
    def _release_shared_client(cls, connection_string: str) -> None:
        client: MongoClient | None = None
        with cls._client_lock:
            ref_count = cls._client_ref_counts.get(connection_string)
            if ref_count is None:
                return
            ref_count -= 1
            if ref_count <= 0:
                cls._client_ref_counts.pop(connection_string, None)
                client = cls._client_cache.pop(connection_string, None)
            else:
                cls._client_ref_counts[connection_string] = ref_count
        if client is not None:
            client.close()

    @classmethod
    def _close_all_clients(cls) -> None:
        with cls._client_lock:
            clients = list(cls._client_cache.values())
            cls._client_cache.clear()
            cls._client_ref_counts.clear()
        for client in clients:
            client.close()

    def _release_client(self) -> None:
        if self._client is None or self._client_key is None:
            return
        type(self)._release_shared_client(self._client_key)
        self._client = None
        self._collection = None
        self._client_key = None

    def _ensure_collection(self) -> None:
        """Ensure the MongoDB collection is initialised."""
        if self._client is None:
            self._client = self._get_shared_client(self.connection_string)
            self._client_key = self.connection_string
        elif self._client_key and self._client_key != self.connection_string:
            self._release_client()
            self._client = self._get_shared_client(self.connection_string)
            self._client_key = self.connection_string
        if self._client is None:
            msg = "MongoDB client could not be initialized"
            raise RuntimeError(msg)
        self._collection = self._client[self.database][self.collection]

    def _execute_operation(
        self,
        *,
        context: str,
        operation: Callable[[], Any],
    ) -> Any:
        try:
            return operation()
        except (
            AutoReconnect,
            ConnectionFailure,
            NetworkTimeout,
            ServerSelectionTimeoutError,
        ) as exc:
            msg = f"MongoDB network error during {context}."
            raise RuntimeError(msg) from exc
        except OperationFailure as exc:
            auth_error_codes = {13, 18}
            if exc.code in auth_error_codes:
                msg = f"MongoDB authentication/authorization error during {context}."
            else:
                msg = f"MongoDB operation error during {context}."
            raise RuntimeError(msg) from exc
        except ConfigurationError as exc:
            msg = f"MongoDB configuration error during {context}."
            raise RuntimeError(msg) from exc
        except PyMongoError as exc:
            msg = f"MongoDB error during {context}."
            raise RuntimeError(msg) from exc

    def __del__(self) -> None:
        """Automatic cleanup when object is garbage collected."""
        self._release_client()


@registry.register(
    NodeMetadata(
        name="MongoDBNode",
        description="MongoDB node",
        category="mongodb",
    )
)
class MongoDBNode(MongoDBClientNode):
    """MongoDB node.

    To use this node, you need to set the following parameters:
    - connection_string: Required.
    """

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
    filter: dict[str, Any] | str | None = Field(
        default=None, description="Filter document for query/update operations"
    )
    update: dict[str, Any] | str | None = Field(
        default=None, description="Update document for update operations"
    )
    pipeline: list[dict[str, Any]] | None = Field(
        default=None, description="Aggregation pipeline for aggregate operations"
    )
    sort: dict[str, int] | list[tuple[str, int]] | None = Field(
        default=None, description="Sort specification for find operations"
    )
    limit: int | str | None = Field(
        default=None, description="Limit for find operations"
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional pymongo options passed to the operation",
    )

    @field_validator("limit", mode="before")
    @classmethod
    def _validate_limit(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            if "{{" in value and "}}" in value:
                return value
            try:
                value = int(value)
            except ValueError as exc:
                msg = "limit must be an integer"
                raise ValueError(msg) from exc
        if isinstance(value, int) and value < 0:
            msg = "limit must be >= 0"
            raise ValueError(msg)
        return value

    def _resolve_filter(self) -> dict[str, Any]:
        """Resolve a filter document from structured or legacy inputs.

        Prefers the structured ``filter`` field, falls back to ``query`` when
        provided as a dict, otherwise defaults to an empty filter.
        """
        if self.filter is not None:
            if isinstance(self.filter, str):
                msg = "filter must resolve to a dict before execution"
                raise ValueError(msg)
            return dict(self.filter)
        if isinstance(self.query, dict):
            return dict(self.query)
        return {}

    def _resolve_update(self) -> dict[str, Any]:
        """Resolve an update/replacement document from inputs."""
        if self.update is not None:
            if isinstance(self.update, str):
                msg = "update must resolve to a dict before execution"
                raise ValueError(msg)
            return dict(self.update)
        if isinstance(self.query, dict):  # pragma: no branch
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
        if isinstance(self.query, dict):  # pragma: no branch
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
            pipeline = self._coerce_object_ids(self._resolve_pipeline())
            return [pipeline], dict(self.options)

        if self.operation in update_operations:
            filter_doc = self._coerce_object_ids(self._resolve_filter())
            update_doc = self._coerce_object_ids(self._resolve_update())
            return [filter_doc, update_doc], dict(self.options)

        if self.operation in filter_operations:
            filter_doc = self._coerce_object_ids(self._resolve_filter())
            kwargs = dict(self.options)
            if self.operation in find_operations:  # pragma: no branch
                if self.sort is not None:
                    kwargs["sort"] = self._normalize_sort(self.sort)
                if self.limit is not None:
                    kwargs["limit"] = self._resolve_limit()
            return [filter_doc], kwargs

        return [self.query], dict(self.options)

    def _resolve_limit(self) -> int:
        limit = self.limit
        if isinstance(limit, str):
            if "{{" in limit and "}}" in limit:
                msg = "limit must resolve to an integer before execution"
                raise ValueError(msg)
            try:
                return int(limit)
            except ValueError as exc:
                msg = "limit must be an integer"
                raise ValueError(msg) from exc
        if limit is None:
            msg = "limit is not set for find operations"
            raise ValueError(msg)
        return limit

    @classmethod
    def _coerce_object_id_value(cls, value: Any) -> Any:
        if isinstance(value, str) and ObjectId.is_valid(value):
            return ObjectId(value)
        if isinstance(value, list):
            return [cls._coerce_object_id_value(item) for item in value]
        if isinstance(value, dict):
            return {
                key: cls._coerce_object_id_value(item) for key, item in value.items()
            }
        return value

    @classmethod
    def _coerce_object_ids(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    cls._coerce_object_id_value(item)
                    if key == "_id"
                    else cls._coerce_object_ids(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._coerce_object_ids(item) for item in value]
        return value

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

        return self._encode_bson(converted_result)

    async def run(self, state: State, config: RunnableConfig) -> dict:
        """Run the MongoDB node with persistent session."""
        context = (
            f"operation={self.operation}, "
            f"database={self.database}, "
            f"collection={self.collection}"
        )

        self._ensure_collection()
        assert self._collection is not None

        def _operation() -> Any:
            operation = getattr(self._collection, self.operation)
            args, kwargs = self._build_operation_call()
            return operation(*args, **kwargs)

        result = self._execute_operation(context=context, operation=_operation)
        return {"data": self._convert_result_to_dict(result)}


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

    def _resolve_filter(self) -> dict[str, Any]:
        if self.filter is None:
            msg = "filter is required for update_many operations"
            raise ValueError(msg)
        return dict(self.filter)

    def _resolve_update(self) -> dict[str, Any]:
        if self.update is None:
            msg = "update is required for update_many operations"
            raise ValueError(msg)
        if not self.update:
            msg = "update must not be empty for update_many operations"
            raise ValueError(msg)
        return dict(self.update)


__all__ = [
    "MongoDBAggregateNode",
    "MongoDBFindNode",
    "MongoDBNode",
    "MongoDBUpdateManyNode",
]

atexit.register(MongoDBNode._close_all_clients)
