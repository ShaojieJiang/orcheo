"""User feedback collection, ingestion, and data augmentation nodes."""

from __future__ import annotations
import time
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="UserFeedbackCollectionNode",
        description="Normalize and validate explicit user feedback.",
        category="conversational_search",
    )
)
class UserFeedbackCollectionNode(TaskNode):
    """Collect user ratings and free-form comments."""

    rating_key: str = Field(default="rating")
    comment_key: str = Field(default="comment")
    session_id_key: str = Field(default="session_id")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Validate and normalize a single piece of user feedback."""
        inputs = state.get("inputs", {})
        rating = inputs.get(self.rating_key)
        if not isinstance(rating, int | float) or not 1 <= rating <= 5:
            msg = "UserFeedbackCollectionNode requires rating between 1 and 5"
            raise ValueError(msg)

        feedback = {
            "session_id": inputs.get(self.session_id_key, "unknown"),
            "rating": float(rating),
            "comment": str(inputs.get(self.comment_key, "")).strip(),
            "timestamp": time.time(),
        }
        return {"feedback": feedback}


@registry.register(
    NodeMetadata(
        name="FeedbackIngestionNode",
        description="Persist feedback entries with deduplication.",
        category="conversational_search",
    )
)
class FeedbackIngestionNode(TaskNode):
    """Ingest user feedback into an in-memory buffer."""

    feedback_key: str = Field(default="feedback")
    store: list[dict[str, Any]] = Field(default_factory=list)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Store feedback entries while avoiding duplicates."""
        feedback = state.get("inputs", {}).get(self.feedback_key)
        if feedback is None:
            return {"ingested": 0, "store_size": len(self.store)}

        entries = feedback if isinstance(feedback, list) else [feedback]
        ingested = 0
        existing_keys = {self._dedupe_key(item) for item in self.store}
        for entry in entries:
            key = self._dedupe_key(entry)
            if key in existing_keys:
                continue
            self.store.append(entry)
            existing_keys.add(key)
            ingested += 1

        return {"ingested": ingested, "store_size": len(self.store)}

    def _dedupe_key(self, entry: dict[str, Any]) -> tuple[Any, Any, Any]:
        return (
            entry.get("session_id"),
            entry.get("rating"),
            entry.get("comment"),
        )


@registry.register(
    NodeMetadata(
        name="DataAugmentationNode",
        description="Generate synthetic variants of dataset entries.",
        category="conversational_search",
    )
)
class DataAugmentationNode(TaskNode):
    """Create lightweight augmented examples for experimentation."""

    dataset_key: str = Field(default="dataset")
    multiplier: int | str = Field(default=1)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Create augmented dataset variants using deterministic templates."""
        multiplier = int(self.multiplier)
        dataset = state.get("inputs", {}).get(self.dataset_key)
        if not isinstance(dataset, list):
            msg = "DataAugmentationNode expects dataset list"
            raise ValueError(msg)

        augmented: list[dict[str, Any]] = []
        for example in dataset:
            for i in range(multiplier):
                augmented.append(self._augment_example(example, i))

        return {"augmented_dataset": augmented, "augmented_count": len(augmented)}

    def _augment_example(self, example: dict[str, Any], index: int) -> dict[str, Any]:
        query = str(example.get("query", ""))
        augmented_query = f"{query} (variant {index + 1}: please elaborate)".strip()
        return {
            **example,
            "query": augmented_query,
            "augmented": True,
            "variant_index": index + 1,
        }
