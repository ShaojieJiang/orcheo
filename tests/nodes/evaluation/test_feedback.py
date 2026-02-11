"""Tests for feedback collection, ingestion, and augmentation nodes."""

import pytest
from orcheo.graph.state import State
from orcheo.nodes.evaluation.feedback import (
    DataAugmentationNode,
    FeedbackIngestionNode,
    UserFeedbackCollectionNode,
)


@pytest.mark.asyncio
async def test_feedback_collection_and_ingestion() -> None:
    collector = UserFeedbackCollectionNode(name="collector")
    feedback = await collector.run(
        State(inputs={"rating": 4, "comment": "Nice", "session_id": "s1"}),
        {},
    )
    ingestor = FeedbackIngestionNode(name="ingestor")
    ingestion_result = await ingestor.run(State(inputs=feedback), {})
    assert ingestion_result["ingested"] == 1


@pytest.mark.asyncio
async def test_user_feedback_requires_valid_rating() -> None:
    node = UserFeedbackCollectionNode(name="collector")
    with pytest.raises(ValueError, match="rating between 1 and 5"):
        await node.run(State(inputs={"rating": 0}), {})


@pytest.mark.asyncio
async def test_feedback_ingestion_handles_none_and_duplicates() -> None:
    node = FeedbackIngestionNode(name="ingestor")
    result = await node.run(State(inputs={}), {})
    assert result["ingested"] == 0
    assert result["store_size"] == 0

    entry = {"session_id": "s1", "rating": 5, "comment": "Nice"}
    first = await node.run(State(inputs={"feedback": entry}), {})
    assert first["ingested"] == 1
    second = await node.run(State(inputs={"feedback": entry}), {})
    assert second["ingested"] == 0
    assert second["store_size"] == 1


@pytest.mark.asyncio
async def test_augmentation_enriches_examples() -> None:
    augmenter = DataAugmentationNode(name="augment", multiplier=2)
    augmented = await augmenter.run(
        State(inputs={"dataset": [{"query": "origin"}]}), {}
    )
    assert augmented["augmented_count"] == 2
    assert all(entry["augmented"] for entry in augmented["augmented_dataset"])


@pytest.mark.asyncio
async def test_data_augmentation_requires_dataset_list() -> None:
    node = DataAugmentationNode(name="augment")
    with pytest.raises(ValueError, match="expects dataset list"):
        await node.run(State(inputs={"dataset": "bad"}), {})
