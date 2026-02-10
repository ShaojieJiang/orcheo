"""Conversational batch evaluation node."""

from __future__ import annotations
import logging
from collections.abc import Mapping
from typing import Any
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import StateGraph
from pydantic import ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


logger = logging.getLogger(__name__)


@registry.register(
    NodeMetadata(
        name="ConversationalBatchEvalNode",
        description=(
            "Iterate conversations and turns through a pipeline, "
            "collecting predictions paired with gold labels"
        ),
        category="evaluation",
    )
)
class ConversationalBatchEvalNode(TaskNode):
    """Iterate conversations and turns, collecting predictions and references.

    When ``pipeline`` is provided, each turn is fed through the pipeline
    sub-graph (e.g. QueryRewriteNode, or a full retrieval-generation chain)
    and the prediction is extracted from the last node's output.  When
    ``pipeline`` is empty, the node operates in passthrough mode and
    extracts the prediction directly from the turn data.
    """

    conversations_key: str = Field(default="conversations")
    prediction_field: str = Field(
        default="query",
        description="Field name in pipeline output containing the prediction",
    )
    gold_field: str = Field(
        default="gold_rewrite",
        description="Field name in turn data containing the gold label",
    )
    max_conversations: int | None = Field(
        default=None,
        ge=1,
        description="Limit number of conversations to evaluate",
    )
    pipeline: SkipJsonSchema[StateGraph | None] = Field(
        default=None,
        description=(
            "Optional pipeline sub-graph executed once per turn. "
            "When omitted, the node runs in passthrough mode."
        ),
    )
    _compiled_pipeline: SkipJsonSchema[Runnable | None] = None

    def get_compiled_pipeline(self) -> Runnable | None:
        """Return a cached compiled pipeline graph when configured."""
        if self.pipeline is None:
            return None
        if self._compiled_pipeline is None:
            self._compiled_pipeline = self.pipeline.compile()
        return self._compiled_pipeline

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Iterate conversations, collect predictions and gold references."""
        inputs = state.get("inputs", {})
        conversations = inputs.get(self.conversations_key)
        if not isinstance(conversations, list):
            msg = "ConversationalBatchEvalNode expects conversations list"
            raise ValueError(msg)

        if self.max_conversations is not None:
            conversations = conversations[: self.max_conversations]

        predictions: list[str] = []
        references: list[str] = []
        per_conversation: dict[str, dict[str, Any]] = {}

        for conv in conversations:
            conv_id = conv.get("conversation_id", "unknown")
            turns = conv.get("turns", [])
            conv_predictions: list[str] = []
            conv_references: list[str] = []
            history: list[str] = []

            for turn in turns:
                gold = str(turn.get(self.gold_field, ""))
                prediction = await self._process_turn(turn, history, state, config)

                predictions.append(prediction)
                references.append(gold)
                conv_predictions.append(prediction)
                conv_references.append(gold)

                user_utterance = turn.get(
                    "raw_question", turn.get("user_utterance", "")
                )
                history.append(str(user_utterance))

            per_conversation[conv_id] = {
                "predictions": conv_predictions,
                "references": conv_references,
                "num_turns": len(turns),
            }

        # Write to state["inputs"] so downstream metric nodes can read them.
        inputs["predictions"] = predictions
        inputs["references"] = references

        return {
            "predictions": predictions,
            "references": references,
            "per_conversation": per_conversation,
            "total_turns": len(predictions),
            "total_conversations": len(conversations),
        }

    async def _process_turn(
        self,
        turn: dict[str, Any],
        history: list[str],
        parent_state: State,
        config: RunnableConfig,
    ) -> str:
        """Run a single turn through the pipeline or passthrough.

        In pipeline mode, builds a per-turn state and invokes each pipeline
        node sequentially, threading results through.  In passthrough mode,
        returns the raw field value from the turn data.
        """
        compiled_pipeline = self.get_compiled_pipeline()
        if compiled_pipeline is None:
            return self._passthrough(turn)

        user_query = turn.get("raw_question", turn.get("user_utterance", ""))

        turn_state = State(
            messages=[],
            inputs={
                "message": str(user_query),
                "query": str(user_query),
                "history": list(history),
            },
            results={},
            structured_response=None,
            config=parent_state.get("config"),
        )

        result_state = await compiled_pipeline.ainvoke(turn_state, config=config)
        return self._extract_prediction(result_state, str(user_query))

    def _extract_prediction(self, result_state: Any, fallback: str) -> str:
        """Extract the prediction field from compiled graph output."""
        if not isinstance(result_state, Mapping):
            return fallback

        prediction = self._extract_from_mapping(result_state)
        if prediction is not None:
            return prediction

        results = result_state.get("results")
        if isinstance(results, Mapping):
            for value in reversed(list(results.values())):
                if isinstance(value, Mapping):
                    prediction = self._extract_from_mapping(value)
                    if prediction is not None:
                        return prediction

        inputs = result_state.get("inputs")
        if isinstance(inputs, Mapping):
            prediction = self._extract_from_mapping(inputs)
            if prediction is not None:
                return prediction

        return fallback

    def _extract_from_mapping(self, payload: Mapping[str, Any]) -> str | None:
        value = payload.get(self.prediction_field)
        if value is None:
            return None
        return str(value)

    def _passthrough(self, turn: dict[str, Any]) -> str:
        """Extract prediction directly from turn data (no pipeline)."""
        prediction = turn.get(self.prediction_field)
        if prediction is not None:
            return str(prediction)
        return str(turn.get("raw_question", turn.get("user_utterance", "")))

    model_config = ConfigDict(arbitrary_types_allowed=True)
