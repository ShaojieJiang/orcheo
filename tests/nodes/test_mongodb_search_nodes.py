"""Tests for MongoDB Atlas Search nodes."""

from __future__ import annotations
import pytest
from bson import ObjectId
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.mongodb import (
    MongoDBEnsureSearchIndexNode,
    MongoDBEnsureVectorIndexNode,
    MongoDBHybridSearchNode,
)


def _base_state() -> State:
    return State(messages=[], inputs={}, results={})


@pytest.mark.asyncio
async def test_ensure_search_index_creates_when_missing(mongo_context) -> None:
    mongo_context.collection.list_search_indexes.return_value = []

    node = MongoDBEnsureSearchIndexNode(
        name="ensure_search",
        database="test_db",
        collection="test_coll",
        definition={"mappings": {"dynamic": False}},
    )

    result = await node.run(_base_state(), RunnableConfig())

    assert result == {"status": "created", "index_name": "orcheo_test_coll_fts"}
    mongo_context.collection.create_search_index.assert_called_once_with(
        {
            "name": "orcheo_test_coll_fts",
            "definition": {"mappings": {"dynamic": False}},
        }
    )


@pytest.mark.asyncio
async def test_ensure_search_index_updates_on_mismatch(mongo_context) -> None:
    mongo_context.collection.list_search_indexes.return_value = [
        {
            "name": "orcheo_test_coll_fts",
            "definition": {"mappings": {"dynamic": True}},
        }
    ]

    node = MongoDBEnsureSearchIndexNode(
        name="ensure_search",
        database="test_db",
        collection="test_coll",
        definition={"mappings": {"dynamic": False}},
        mode="ensure_or_update",
    )

    result = await node.run(_base_state(), RunnableConfig())

    assert result == {"status": "updated", "index_name": "orcheo_test_coll_fts"}
    mongo_context.collection.update_search_index.assert_called_once_with(
        "orcheo_test_coll_fts", {"mappings": {"dynamic": False}}
    )


@pytest.mark.asyncio
async def test_ensure_search_index_skips_in_ensure_mode(mongo_context) -> None:
    mongo_context.collection.list_search_indexes.return_value = [
        {
            "name": "orcheo_test_coll_fts",
            "definition": {"mappings": {"dynamic": True}},
        }
    ]

    node = MongoDBEnsureSearchIndexNode(
        name="ensure_search",
        database="test_db",
        collection="test_coll",
        definition={"mappings": {"dynamic": False}},
        mode="ensure",
    )

    result = await node.run(_base_state(), RunnableConfig())

    assert result == {"status": "skipped", "index_name": "orcheo_test_coll_fts"}
    mongo_context.collection.update_search_index.assert_not_called()
    mongo_context.collection.create_search_index.assert_not_called()


@pytest.mark.asyncio
async def test_force_rebuild_drops_and_creates(mongo_context) -> None:
    mongo_context.collection.list_search_indexes.return_value = [
        {
            "name": "orcheo_test_coll_fts",
            "definition": {"mappings": {"dynamic": True}},
        }
    ]

    node = MongoDBEnsureSearchIndexNode(
        name="ensure_search",
        database="test_db",
        collection="test_coll",
        definition={"mappings": {"dynamic": False}},
        mode="force_rebuild",
    )

    result = await node.run(_base_state(), RunnableConfig())

    assert result == {"status": "created", "index_name": "orcheo_test_coll_fts"}
    mongo_context.collection.drop_search_index.assert_called_once_with(
        "orcheo_test_coll_fts"
    )
    mongo_context.collection.create_search_index.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_search_index_uses_definition_name(mongo_context) -> None:
    mongo_context.collection.list_search_indexes.return_value = []

    node = MongoDBEnsureSearchIndexNode(
        name="ensure_search",
        database="test_db",
        collection="test_coll",
        definition={
            "name": "custom_search",
            "definition": {"mappings": {"dynamic": False}},
        },
    )

    result = await node.run(_base_state(), RunnableConfig())

    assert result == {"status": "created", "index_name": "custom_search"}
    mongo_context.collection.create_search_index.assert_called_once_with(
        {
            "name": "custom_search",
            "definition": {"mappings": {"dynamic": False}},
        }
    )


@pytest.mark.asyncio
async def test_vector_index_builds_definition_when_missing(mongo_context) -> None:
    mongo_context.collection.list_search_indexes.return_value = []

    node = MongoDBEnsureVectorIndexNode(
        name="ensure_vector",
        database="test_db",
        collection="test_coll",
        dimensions=3,
        similarity="cosine",
        path="embedding",
    )

    result = await node.run(_base_state(), RunnableConfig())

    assert result == {"status": "created", "index_name": "orcheo_test_coll_vec"}
    mongo_context.collection.create_search_index.assert_called_once_with(
        {
            "name": "orcheo_test_coll_vec",
            "definition": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "embedding": {
                            "type": "vector",
                            "numDimensions": 3,
                            "similarity": "cosine",
                        }
                    },
                }
            },
        }
    )


@pytest.mark.asyncio
async def test_ensure_vector_index_uses_definition_name(mongo_context) -> None:
    mongo_context.collection.list_search_indexes.return_value = []

    node = MongoDBEnsureVectorIndexNode(
        name="ensure_vector",
        database="test_db",
        collection="test_coll",
        definition={
            "name": "custom_vector",
            "definition": {"mappings": {"dynamic": False}},
        },
    )

    result = await node.run(_base_state(), RunnableConfig())

    assert result == {"status": "created", "index_name": "custom_vector"}
    mongo_context.collection.create_search_index.assert_called_once_with(
        {
            "name": "custom_vector",
            "definition": {"mappings": {"dynamic": False}},
        }
    )


def test_hybrid_search_builds_union_pipeline() -> None:
    node = MongoDBHybridSearchNode(
        name="hybrid",
        database="test_db",
        collection="test_coll",
        text_query="hello",
        vector=[0.1, 0.2],
        text_paths=["body"],
        vector_path="embedding",
        top_k=3,
    )

    pipeline = node._build_pipeline()
    assert pipeline[0]["$search"]["text"]["query"] == "hello"

    union_stage = next(stage for stage in pipeline if "$unionWith" in stage)
    vector_pipeline = union_stage["$unionWith"]["pipeline"]
    assert vector_pipeline[0]["$vectorSearch"]["queryVector"] == [0.1, 0.2]

    group_stage = next(stage for stage in pipeline if "$group" in stage)
    assert group_stage["$group"]["score"] == {"$sum": "$rrf_score"}


def test_hybrid_search_builds_text_only_pipeline() -> None:
    node = MongoDBHybridSearchNode(
        name="hybrid",
        database="test_db",
        collection="test_coll",
        text_query="hello",
        vector=None,
        text_paths=["body"],
        vector_path="embedding",
        top_k=3,
    )

    pipeline = node._build_pipeline()
    assert pipeline[0]["$search"]["text"]["query"] == "hello"
    assert all("$unionWith" not in stage for stage in pipeline)


def test_hybrid_search_builds_vector_only_pipeline() -> None:
    node = MongoDBHybridSearchNode(
        name="hybrid",
        database="test_db",
        collection="test_coll",
        text_query=None,
        vector=[0.1, 0.2],
        text_paths=["body"],
        vector_path="embedding",
        top_k=3,
    )

    pipeline = node._build_pipeline()
    assert pipeline[0]["$vectorSearch"]["queryVector"] == [0.1, 0.2]
    assert all("$unionWith" not in stage for stage in pipeline)


@pytest.mark.asyncio
async def test_hybrid_search_normalizes_results(mongo_context) -> None:
    object_id = ObjectId("507f1f77bcf86cd799439011")
    mongo_context.collection.aggregate.return_value = [
        {"_id": object_id, "score": 1.5, "title": "Doc"}
    ]

    node = MongoDBHybridSearchNode(
        name="hybrid",
        database="test_db",
        collection="test_coll",
        text_query="hello",
        vector=None,
        text_paths=["body"],
        vector_path="embedding",
        top_k=3,
    )

    result = await node.run(_base_state(), RunnableConfig())

    assert result["results"] == [
        {
            "id": str(object_id),
            "score": 1.5,
            "raw": {"_id": str(object_id), "title": "Doc"},
        }
    ]


def test_hybrid_search_requires_query_or_vector() -> None:
    node = MongoDBHybridSearchNode(
        name="hybrid",
        database="test_db",
        collection="test_coll",
        text_query=None,
        vector=None,
        text_paths=["body"],
        vector_path="embedding",
    )

    with pytest.raises(ValueError, match="requires text_query or vector"):
        node._build_pipeline()
