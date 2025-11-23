"""Evaluation, analytics, compliance, and augmentation nodes."""

from __future__ import annotations
import math
import re
import time
from collections import defaultdict
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.conversation import MemoryTurn
from orcheo.nodes.registry import NodeMetadata, registry


def _tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"\W+", text.lower()) if token]


@registry.register(
    NodeMetadata(
        name="DatasetNode",
        description="Load and filter golden datasets for evaluation workflows.",
        category="conversational_search",
    )
)
class DatasetNode(TaskNode):
    """Load a dataset from inputs or a built-in fallback."""

    dataset_key: str = Field(default="dataset")
    split_key: str = Field(default="split")
    dataset: list[dict[str, Any]] = Field(default_factory=list)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a dataset filtered by split and limited when requested."""
        inputs = state.get("inputs", {})
        dataset = inputs.get(self.dataset_key, self.dataset)
        if not isinstance(dataset, list):
            msg = "DatasetNode expects dataset to be a list"
            raise ValueError(msg)

        split = inputs.get(self.split_key)
        if isinstance(split, str):
            dataset = [row for row in dataset if row.get("split") == split]

        limit = inputs.get("limit")
        if isinstance(limit, int) and limit > 0:
            dataset = dataset[:limit]

        return {"dataset": dataset, "count": len(dataset)}


@registry.register(
    NodeMetadata(
        name="RetrievalEvaluationNode",
        description="Compute retrieval quality metrics for search results.",
        category="conversational_search",
    )
)
class RetrievalEvaluationNode(TaskNode):
    """Evaluate retrieval outputs against golden relevance labels."""

    dataset_key: str = Field(default="dataset")
    results_key: str = Field(default="retrieval_results")
    k: int = Field(default=5, ge=1)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compute retrieval metrics across the provided dataset."""
        inputs = state.get("inputs", {})
        dataset = inputs.get(self.dataset_key)
        results = inputs.get(self.results_key)
        if not isinstance(dataset, list) or not isinstance(results, list):
            msg = "RetrievalEvaluationNode requires dataset and retrieval_results lists"
            raise ValueError(msg)

        per_query: dict[str, dict[str, float]] = {}
        recalls: list[float] = []
        mrrs: list[float] = []
        ndcgs: list[float] = []
        maps: list[float] = []

        result_map = {row.get("query_id"): row.get("results", []) for row in results}
        for example in dataset:
            query_id = example.get("id")
            relevant_ids: set[str] = set(example.get("relevant_ids", []))
            returned = result_map.get(query_id, [])[: self.k]
            ranked_ids = [
                item["id"]
                for item in returned
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
            recall = self._recall_at_k(ranked_ids, relevant_ids)
            mrr = self._mrr(ranked_ids, relevant_ids)
            ndcg = self._ndcg(ranked_ids, relevant_ids)
            average_precision = self._average_precision(ranked_ids, relevant_ids)

            per_query[str(query_id)] = {
                "recall_at_k": recall,
                "mrr": mrr,
                "ndcg": ndcg,
                "map": average_precision,
            }
            recalls.append(recall)
            mrrs.append(mrr)
            ndcgs.append(ndcg)
            maps.append(average_precision)

        return {
            "metrics": {
                "recall_at_k": sum(recalls) / len(recalls) if recalls else 0.0,
                "mrr": sum(mrrs) / len(mrrs) if mrrs else 0.0,
                "ndcg": sum(ndcgs) / len(ndcgs) if ndcgs else 0.0,
                "map": sum(maps) / len(maps) if maps else 0.0,
            },
            "per_query": per_query,
        }

    def _recall_at_k(self, ranked_ids: list[str], relevant_ids: set[str]) -> float:
        if not relevant_ids:
            return 0.0
        hits = sum(1 for item in ranked_ids if item in relevant_ids)
        return hits / len(relevant_ids)

    def _mrr(self, ranked_ids: list[str], relevant_ids: set[str]) -> float:
        for index, item_id in enumerate(ranked_ids):
            if item_id in relevant_ids:
                return 1.0 / (index + 1)
        return 0.0

    def _ndcg(self, ranked_ids: list[str], relevant_ids: set[str]) -> float:
        if not relevant_ids:
            return 0.0
        dcg = 0.0
        for index, item_id in enumerate(ranked_ids):
            if item_id in relevant_ids:
                dcg += 1.0 / math.log2(index + 2)
        ideal_hits = min(len(relevant_ids), len(ranked_ids))
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
        if idcg == 0:
            return 0.0
        return dcg / idcg

    def _average_precision(
        self, ranked_ids: list[str], relevant_ids: set[str]
    ) -> float:
        if not relevant_ids:
            return 0.0
        hits = 0
        precision_sum = 0.0
        for index, item_id in enumerate(ranked_ids, start=1):
            if item_id in relevant_ids:
                hits += 1
                precision_sum += hits / index
        if hits == 0:
            return 0.0
        return precision_sum / len(relevant_ids)


@registry.register(
    NodeMetadata(
        name="AnswerQualityEvaluationNode",
        description="Score generated answers against reference answers.",
        category="conversational_search",
    )
)
class AnswerQualityEvaluationNode(TaskNode):
    """Compute heuristic faithfulness and relevance scores."""

    references_key: str = Field(default="references")
    answers_key: str = Field(default="answers")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score answers against references using overlap heuristics."""
        inputs = state.get("inputs", {})
        references = inputs.get(self.references_key)
        answers = inputs.get(self.answers_key)
        if not isinstance(references, dict) or not isinstance(answers, list):
            msg = "AnswerQualityEvaluationNode expects references dict and answers list"
            raise ValueError(msg)

        per_answer: dict[str, dict[str, float]] = {}
        faithfulness_scores: list[float] = []
        relevance_scores: list[float] = []

        for entry in answers:
            answer_id = entry.get("id")
            answer_text = entry.get("answer", "")
            reference = references.get(answer_id, "")
            faithfulness = self._overlap_score(answer_text, reference)
            relevance = self._relevance_score(answer_text, reference)
            per_answer[str(answer_id)] = {
                "faithfulness": faithfulness,
                "relevance": relevance,
            }
            faithfulness_scores.append(faithfulness)
            relevance_scores.append(relevance)

        return {
            "metrics": {
                "faithfulness": sum(faithfulness_scores) / len(faithfulness_scores)
                if faithfulness_scores
                else 0.0,
                "relevance": sum(relevance_scores) / len(relevance_scores)
                if relevance_scores
                else 0.0,
            },
            "per_answer": per_answer,
        }

    def _overlap_score(self, answer: str, reference: str) -> float:
        answer_tokens = set(_tokenize(answer))
        reference_tokens = set(_tokenize(reference))
        if not reference_tokens:
            return 0.0
        overlap = len(answer_tokens & reference_tokens)
        return overlap / len(reference_tokens)

    def _relevance_score(self, answer: str, reference: str) -> float:
        if not answer.strip() or not reference.strip():
            return 0.0
        answer_tokens = _tokenize(answer)
        reference_tokens = _tokenize(reference)
        shared = sum(1 for token in answer_tokens if token in reference_tokens)
        return shared / max(len(answer_tokens), 1)


@registry.register(
    NodeMetadata(
        name="LLMJudgeNode",
        description="Apply lightweight, rule-based LLM judging heuristics.",
        category="conversational_search",
    )
)
class LLMJudgeNode(TaskNode):
    """Simulate LLM-as-a-judge with transparent heuristics."""

    answers_key: str = Field(default="answers")
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Apply lightweight judging heuristics to answers."""
        answers = state.get("inputs", {}).get(self.answers_key)
        if not isinstance(answers, list):
            msg = "LLMJudgeNode expects answers list"
            raise ValueError(msg)

        verdicts: list[dict[str, Any]] = []
        passing = 0
        for entry in answers:
            answer_id = entry.get("id")
            content = str(entry.get("answer", ""))
            score = self._score(content)
            verdict = {
                "id": answer_id,
                "score": score,
                "approved": score >= self.min_score,
                "flags": self._flags(content),
            }
            passing += int(verdict["approved"])
            verdicts.append(verdict)

        return {
            "approved_ratio": passing / len(verdicts) if verdicts else 0.0,
            "verdicts": verdicts,
        }

    def _score(self, content: str) -> float:
        tokens = _tokenize(content)
        if not tokens:
            return 0.0
        penalties = sum(
            token in {"hallucination", "unsafe", "ignore"} for token in tokens
        )
        coverage_bonus = min(len(tokens) / 50, 0.4)
        base = 0.6 + coverage_bonus - 0.15 * penalties
        return max(min(base, 1.0), 0.0)

    def _flags(self, content: str) -> list[str]:
        flags: list[str] = []
        if re.search(r"\b(unsafe|ignore safety)\b", content, re.IGNORECASE):
            flags.append("safety")
        if "???" in content or "lorem ipsum" in content.lower():
            flags.append("low_confidence")
        return flags


@registry.register(
    NodeMetadata(
        name="FailureAnalysisNode",
        description="Categorize evaluation failures for triage.",
        category="conversational_search",
    )
)
class FailureAnalysisNode(TaskNode):
    """Label evaluation outputs with failure categories."""

    retrieval_metrics_key: str = Field(default="retrieval_metrics")
    answer_metrics_key: str = Field(default="answer_metrics")
    feedback_key: str = Field(default="feedback")
    recall_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    faithfulness_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Flag failure categories using metrics and feedback signals."""
        inputs = state.get("inputs", {})
        retrieval_metrics = inputs.get(self.retrieval_metrics_key, {})
        answer_metrics = inputs.get(self.answer_metrics_key, {})
        feedback = inputs.get(self.feedback_key, []) or []

        categories: set[str] = set()
        if retrieval_metrics.get("recall_at_k", 1.0) < self.recall_threshold:
            categories.add("low_recall")
        if answer_metrics.get("faithfulness", 1.0) < self.faithfulness_threshold:
            categories.add("low_answer_quality")
        if any(entry.get("rating", 5) <= 2 for entry in feedback):
            categories.add("negative_feedback")

        return {"categories": sorted(categories)}


@registry.register(
    NodeMetadata(
        name="ABTestingNode",
        description="Rank variants and gate rollouts using evaluation metrics.",
        category="conversational_search",
    )
)
class ABTestingNode(TaskNode):
    """Select a winning variant while applying rollout gates."""

    variants_key: str = Field(default="variants")
    primary_metric: str = Field(default="score")
    evaluation_metrics_key: str = Field(default="evaluation_metrics")
    min_metric_threshold: float = Field(default=0.5)
    min_feedback_score: float = Field(default=0.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Rank A/B variants and apply rollout gating criteria."""
        inputs = state.get("inputs", {})
        variants = inputs.get(self.variants_key)
        if not isinstance(variants, list) or not variants:
            msg = "ABTestingNode requires a non-empty variants list"
            raise ValueError(msg)

        ranked = sorted(
            variants,
            key=lambda item: item.get(self.primary_metric, 0.0),
            reverse=True,
        )
        winner = ranked[0]

        evaluation_metrics = inputs.get(self.evaluation_metrics_key, {})
        rollout_allowed = bool(
            winner.get(self.primary_metric, 0.0) >= self.min_metric_threshold
        )
        if evaluation_metrics:
            rollout_allowed = rollout_allowed and all(
                value >= self.min_metric_threshold
                for value in evaluation_metrics.values()
            )

        feedback_score = inputs.get("feedback_score")
        if isinstance(feedback_score, (int, float)):
            rollout_allowed = (
                rollout_allowed and feedback_score >= self.min_feedback_score
            )

        return {
            "winner": winner,
            "ranking": ranked,
            "rollout_allowed": rollout_allowed,
        }


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
        if not isinstance(rating, (int, float)) or not 1 <= rating <= 5:
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
        name="AnalyticsExportNode",
        description="Aggregate evaluation metrics and feedback for export.",
        category="conversational_search",
    )
)
class AnalyticsExportNode(TaskNode):
    """Summarize evaluation outputs into a transport-friendly bundle."""

    metrics_key: str = Field(default="metrics")
    feedback_key: str = Field(default="feedback")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Aggregate metrics and feedback into an export payload."""
        metrics = state.get("inputs", {}).get(self.metrics_key, {}) or {}
        feedback = state.get("inputs", {}).get(self.feedback_key, []) or []
        if not isinstance(feedback, list):
            msg = "AnalyticsExportNode expects feedback to be a list when provided"
            raise ValueError(msg)

        ratings = [
            entry.get("rating", 0) for entry in feedback if isinstance(entry, dict)
        ]
        average_rating = sum(ratings) / len(ratings) if ratings else 0.0
        counts: dict[str, int] = defaultdict(int)
        for entry in feedback:
            if category := entry.get("category"):
                counts[str(category)] += 1

        export_payload = {
            "metrics": metrics,
            "feedback_count": len(feedback),
            "average_rating": average_rating,
            "feedback_categories": dict(counts),
        }
        return {"export": export_payload}


@registry.register(
    NodeMetadata(
        name="PolicyComplianceNode",
        description="Apply policy checks and emit audit details.",
        category="conversational_search",
    )
)
class PolicyComplianceNode(TaskNode):
    """Detect basic policy violations and redact sensitive snippets."""

    text_key: str = Field(default="content")
    blocked_terms: list[str] = Field(default_factory=lambda: ["password", "ssn"])

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Apply policy checks and return sanitized content with audit metadata."""
        content = state.get("inputs", {}).get(self.text_key, "")
        if not isinstance(content, str):
            msg = "PolicyComplianceNode expects content string"
            raise ValueError(msg)

        violations = self._detect_violations(content)
        sanitized = self._sanitize(content)
        return {
            "compliant": not violations,
            "violations": violations,
            "sanitized": sanitized,
            "audit_log": [
                {
                    "timestamp": time.time(),
                    "violations": violations,
                    "original_length": len(content),
                    "sanitized_length": len(sanitized),
                }
            ],
        }

    def _detect_violations(self, content: str) -> list[str]:
        violations: list[str] = []
        for term in self.blocked_terms:
            if re.search(rf"\b{re.escape(term)}\b", content, re.IGNORECASE):
                violations.append(f"blocked_term:{term}")
        if re.search(r"\b\d{3}-\d{2}-\d{4}\b", content):
            violations.append("pii:ssn_pattern")
        if re.search(r"\b\S+@\S+\.[a-z]{2,}\b", content, re.IGNORECASE):
            violations.append("pii:email")
        return violations

    def _sanitize(self, content: str) -> str:
        sanitized = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]", content)
        sanitized = re.sub(r"\b\S+@\S+\.[a-z]{2,}\b", "[REDACTED_EMAIL]", sanitized)
        for term in self.blocked_terms:
            sanitized = re.sub(
                rf"\b{re.escape(term)}\b",
                "[REDACTED_TERM]",
                sanitized,
                flags=re.IGNORECASE,
            )
        return sanitized


@registry.register(
    NodeMetadata(
        name="MemoryPrivacyNode",
        description="Enforce redaction and retention for conversation history.",
        category="conversational_search",
    )
)
class MemoryPrivacyNode(TaskNode):
    """Redact sensitive details from stored conversation turns."""

    history_key: str = Field(default="conversation_history")
    retention_count: int | None = Field(default=None, ge=1)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Redact sensitive details and enforce retention limits."""
        history_raw = state.get("inputs", {}).get(self.history_key, []) or []
        if not isinstance(history_raw, list):
            msg = "MemoryPrivacyNode expects a list for conversation_history"
            raise ValueError(msg)

        sanitized_history: list[dict[str, Any]] = []
        redactions = 0
        for turn_data in history_raw:
            turn = MemoryTurn.model_validate(turn_data)
            sanitized_content, turn_redactions = self._redact(turn.content)
            redactions += turn_redactions
            sanitized_history.append(
                {
                    "role": turn.role,
                    "content": sanitized_content,
                    "metadata": turn.metadata,
                }
            )

        if self.retention_count is not None:
            sanitized_history = sanitized_history[-self.retention_count :]

        return {
            "sanitized_history": sanitized_history,
            "redaction_count": redactions,
            "truncated": self.retention_count is not None
            and len(history_raw) > len(sanitized_history),
        }

    def _redact(self, content: str) -> tuple[str, int]:
        patterns = [
            (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
            (r"\b\S+@\S+\.[a-z]{2,}\b", "[REDACTED_EMAIL]"),
            (r"\b\d{10}\b", "[REDACTED_PHONE]"),
        ]
        redactions = 0
        sanitized = content
        for pattern, replacement in patterns:
            sanitized, occurrences = re.subn(pattern, replacement, sanitized)
            redactions += occurrences
        return sanitized, redactions


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
    multiplier: int = Field(default=1, ge=1)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Create augmented dataset variants using deterministic templates."""
        dataset = state.get("inputs", {}).get(self.dataset_key)
        if not isinstance(dataset, list):
            msg = "DataAugmentationNode expects dataset list"
            raise ValueError(msg)

        augmented: list[dict[str, Any]] = []
        for example in dataset:
            for i in range(self.multiplier):
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


@registry.register(
    NodeMetadata(
        name="TurnAnnotationNode",
        description="Annotate conversation turns with heuristics.",
        category="conversational_search",
    )
)
class TurnAnnotationNode(TaskNode):
    """Label conversation turns with semantic hints."""

    history_key: str = Field(default="conversation_history")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Annotate conversation turns with basic heuristics."""
        history_raw = state.get("inputs", {}).get(self.history_key, []) or []
        if not isinstance(history_raw, list):
            msg = "TurnAnnotationNode expects conversation_history list"
            raise ValueError(msg)

        annotations: list[dict[str, Any]] = []
        for turn_data in history_raw:
            turn = MemoryTurn.model_validate(turn_data)
            annotations.append(
                {
                    "role": turn.role,
                    "content": turn.content,
                    "is_question": turn.content.strip().endswith("?"),
                    "sentiment": self._sentiment(turn.content),
                }
            )

        return {"annotations": annotations}

    def _sentiment(self, content: str) -> str:
        lowered = content.lower()
        if any(token in lowered for token in ["thank", "great", "awesome"]):
            return "positive"
        if any(token in lowered for token in ["error", "terrible", "fail"]):
            return "negative"
        return "neutral"
