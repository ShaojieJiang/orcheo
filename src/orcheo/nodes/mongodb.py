"""MongoDB node."""

import os
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pymongo import MongoClient
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
    query: dict = {}
    """The query to pass to the operation."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the MongoDB client."""
        super().__init__(**kwargs)
        self._client: MongoClient = MongoClient(os.getenv("MDB_CONNECTION_STRING"))
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
        operation = getattr(self._collection, self.operation)
        result = operation(self.query)
        return {"data": self._convert_result_to_dict(result)}

    def __del__(self) -> None:
        """Automatic cleanup when object is garbage collected."""
        self._client.close()
