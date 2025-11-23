"""Evaluation, analytics, compliance, and augmentation nodes for conversational search.

This module provides heuristics for research-focused workflows without external
dependencies.
"""

from __future__ import annotations
import math
import time
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


def _normalize_results(results: list[Any]) -> list[SearchResult]:
    normalized: list[SearchResult] = []
    for item in results:
        if isinstance(item, SearchResult):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(SearchResult(**item))
        else:
            msg = "Retrieval results must be SearchResult or dict entries"
            raise ValueError(msg)
    return normalized


def _dcg(relevances: list[int]) -> float:
    if not relevances:
        return 0.0
    return sum(rel / math.log2(index + 2) for index, rel in enumerate(relevances))


def _token_overlap_score(candidate: str, reference: str) -> float:
    candidate_tokens = {token for token in candidate.lower().split() if token}
    reference_tokens = {token for token in reference.lower().split() if token}
    if not reference_tokens:
        return 0.0
    return len(candidate_tokens & reference_tokens) / len(reference_tokens)


@registry.register(
    NodeMetadata(
        name="DatasetNode",
        description="Load and validate evaluation datasets for conversational search.",
        category="conversational_search",
    )
)
class DatasetNode(TaskNode):
    """Load golden datasets with simple schema validation."""

    dataset: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Default dataset used when state inputs do not provide one.",
    )
    dataset_key: str = Field(
        default="dataset",
        description="Key inside ``state.inputs`` with dataset entries.",
    )
    required_fields: set[str] = Field(
        default_factory=lambda: {"query", "relevant_documents", "reference_answer"},
        description="Fields required for every dataset example.",
    )
    limit: int | None = Field(
        default=None,
        gt=0,
        description="Optional cap on the number of examples returned.",
    )
    version: str = Field(default="v1", description="Dataset version identifier.")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Validate dataset structure and return normalized examples."""
        dataset = state.get("inputs", {}).get(self.dataset_key) or self.dataset
        if not dataset:
            msg = "DatasetNode requires at least one dataset example"
            raise ValueError(msg)

        validated: list[dict[str, Any]] = []
        for entry in dataset:
            if not isinstance(entry, dict):
                msg = "Dataset entries must be dictionaries"
                raise ValueError(msg)
            missing_fields = self.required_fields - set(entry.keys())
            if missing_fields:
                msg = f"Dataset entry missing fields: {sorted(missing_fields)}"
                raise ValueError(msg)

            normalized = dict(entry)
            normalized["query"] = str(entry["query"]).strip()
            relevant = entry.get("relevant_documents", [])
            if not isinstance(relevant, list):
                msg = "relevant_documents must be a list"
                raise ValueError(msg)
            normalized["relevant_documents"] = relevant
            validated.append(normalized)
            if self.limit is not None and len(validated) >= self.limit:
                break

        return {
            "dataset": validated,
            "size": len(validated),
            "version": self.version,
            "fields": sorted(self.required_fields),
        }


@registry.register(
    NodeMetadata(
        name="RetrievalEvaluationNode",
        description="Compute retrieval quality metrics (Recall@k, MRR, NDCG, MAP).",
        category="conversational_search",
    )
)
class RetrievalEvaluationNode(TaskNode):
    """Evaluate retrieval results against a labeled dataset."""

    dataset_key: str = Field(
        default="dataset", description="Key for dataset examples containing labels."
    )
    retrievals_key: str = Field(
        default="retrievals", description="Key for retrieval outputs to evaluate."
    )
    top_k: int = Field(default=5, gt=0, description="Depth for Recall@k and NDCG@k.")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compute retrieval metrics across all labeled queries."""
        dataset, retrievals = self._validate_inputs(state)
        ground_truth = self._build_ground_truth(dataset)
        retrieval_map = self._normalize_retrievals(retrievals)

        per_query: list[dict[str, Any]] = []
        recalls: list[float] = []
        mrrs: list[float] = []
        ndcgs: list[float] = []
        maps: list[float] = []

        for query, relevant_ids in ground_truth.items():
            metrics = self._score_query(relevant_ids, retrieval_map.get(query, []))
            per_query.append({"query": query, **metrics})
            recalls.append(metrics["recall"])
            mrrs.append(metrics["mrr"])
            ndcgs.append(metrics["ndcg"])
            maps.append(metrics["map"])

        return {
            "recall@k": self._average(recalls),
            "mrr": self._average(mrrs),
            "ndcg": self._average(ndcgs),
            "map": self._average(maps),
            "per_query": per_query,
        }

    def _validate_inputs(
        self, state: State
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        dataset = state.get("inputs", {}).get(self.dataset_key)
        retrievals = state.get("inputs", {}).get(self.retrievals_key)

        if not isinstance(dataset, list) or not dataset:
            msg = "RetrievalEvaluationNode requires a non-empty dataset list"
            raise ValueError(msg)
        if not isinstance(retrievals, list) or not retrievals:
            msg = "RetrievalEvaluationNode requires retrieval results to score"
            raise ValueError(msg)

        return dataset, retrievals

    def _build_ground_truth(self, dataset: list[dict[str, Any]]) -> dict[str, set[Any]]:
        return {
            str(example.get("query", "")).strip(): set(
                example.get("relevant_documents", [])
            )
            for example in dataset
        }

    def _normalize_retrievals(
        self, retrievals: list[dict[str, Any]]
    ) -> dict[str, list[SearchResult]]:
        retrieval_map: dict[str, list[SearchResult]] = {}
        for retrieval in retrievals:
            if not isinstance(retrieval, dict):
                msg = "Retrieval entries must be dictionaries"
                raise ValueError(msg)
            query = str(retrieval.get("query", "")).strip()
            if not query:
                msg = "Retrieval entries must include a query string"
                raise ValueError(msg)
            results_raw = retrieval.get("results", []) or []
            retrieval_map[query] = _normalize_results(results_raw)
        return retrieval_map

    def _score_query(
        self, relevant_ids: set[Any], results: list[SearchResult]
    ) -> dict[str, Any]:
        retrieved_ids = [result.id for result in results[: self.top_k]]
        hits = [
            identifier for identifier in retrieved_ids if identifier in relevant_ids
        ]
        recall = len(hits) / len(relevant_ids) if relevant_ids else 0.0

        reciprocal_rank = 0.0
        for index, identifier in enumerate(retrieved_ids):
            if identifier in relevant_ids:
                reciprocal_rank = 1.0 / (index + 1)
                break

        gains = [1 if identifier in relevant_ids else 0 for identifier in retrieved_ids]
        ideal_gains = [1] * min(len(relevant_ids), self.top_k)
        ndcg = 0.0
        if ideal_gains:
            ideal_dcg = _dcg(ideal_gains)
            ndcg = _dcg(gains) / ideal_dcg if ideal_dcg else 0.0

        precision_sum = 0.0
        relevant_seen = 0
        for index, identifier in enumerate(retrieved_ids, start=1):
            if identifier in relevant_ids:
                relevant_seen += 1
                precision_sum += relevant_seen / index
        average_precision = precision_sum / len(relevant_ids) if relevant_ids else 0.0

        return {
            "recall": recall,
            "mrr": reciprocal_rank,
            "ndcg": ndcg,
            "map": average_precision,
            "hits": hits,
        }

    @staticmethod
    def _average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0


@registry.register(
    NodeMetadata(
        name="AnswerQualityEvaluationNode",
        description="Score generated answers for faithfulness and relevance.",
        category="conversational_search",
    )
)
class AnswerQualityEvaluationNode(TaskNode):
    """Evaluate answer quality using keyword overlap heuristics."""

    dataset_key: str = Field(
        default="dataset", description="Key containing dataset with references."
    )
    answers_key: str = Field(
        default="answers", description="Key containing generated answers to score."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score generated answers for faithfulness and relevance heuristics."""
        dataset = state.get("inputs", {}).get(self.dataset_key) or []
        answers = state.get("inputs", {}).get(self.answers_key)

        if not isinstance(answers, list) or not answers:
            msg = "AnswerQualityEvaluationNode requires answers to evaluate"
            raise ValueError(msg)

        reference_lookup = {
            str(example.get("query", "")).strip(): str(
                example.get("reference_answer", "")
            ).strip()
            for example in dataset
        }

        per_answer: list[dict[str, Any]] = []
        faithfulness_scores: list[float] = []
        relevance_scores: list[float] = []

        for answer_entry in answers:
            if not isinstance(answer_entry, dict):
                msg = "Answer entries must be dictionaries"
                raise ValueError(msg)
            query = str(answer_entry.get("query", "")).strip()
            answer = str(answer_entry.get("answer", "")).strip()
            reference_answer = reference_lookup.get(query, "")
            context_text = " ".join(map(str, answer_entry.get("context", []))).strip()

            faithfulness = _token_overlap_score(answer, reference_answer)
            relevance = _token_overlap_score(answer, context_text or reference_answer)

            per_answer.append(
                {
                    "query": query,
                    "faithfulness": faithfulness,
                    "relevance": relevance,
                    "reference_used": bool(reference_answer),
                }
            )
            faithfulness_scores.append(faithfulness)
            relevance_scores.append(relevance)

        def _average(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        return {
            "faithfulness": _average(faithfulness_scores),
            "relevance": _average(relevance_scores),
            "per_answer": per_answer,
        }


@registry.register(
    NodeMetadata(
        name="LLMJudgeNode",
        description="Heuristic LLM-as-a-judge simulator for responses.",
        category="conversational_search",
    )
)
class LLMJudgeNode(TaskNode):
    """Approximate LLM judging with lightweight heuristics."""

    answer_key: str = Field(
        default="answer",
        description="Key inside ``state.inputs`` containing the answer.",
    )
    grounding_key: str = Field(
        default="grounding",
        description="Key inside ``state.inputs`` with grounding text.",
    )
    passing_score: float = Field(
        default=0.65, description="Minimum score required for a passing verdict."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Approximate an LLM judge verdict using heuristic signals."""
        answer = str(state.get("inputs", {}).get(self.answer_key, "")).strip()
        grounding = str(state.get("inputs", {}).get(self.grounding_key, "")).strip()
        if not answer:
            msg = "LLMJudgeNode requires an answer to evaluate"
            raise ValueError(msg)

        score = 0.5
        reasons: list[str] = []

        if "[" in answer and "]" in answer:
            score += 0.2
        else:
            reasons.append("Missing explicit citations")

        if grounding and grounding.lower() in answer.lower():
            score += 0.2
        elif not grounding:
            reasons.append("No grounding provided")
        else:
            reasons.append("Answer not clearly grounded")

        if len(answer.split()) > 30:
            score += 0.1
        else:
            reasons.append("Answer too short for confidence")

        verdict = "pass" if score >= self.passing_score else "fail"
        severity = "low" if verdict == "pass" else "high" if score < 0.4 else "medium"

        return {
            "verdict": verdict,
            "score": round(score, 3),
            "reasons": reasons,
            "severity": severity,
        }


@registry.register(
    NodeMetadata(
        name="FailureAnalysisNode",
        description="Categorize failures using evaluation outputs.",
        category="conversational_search",
    )
)
class FailureAnalysisNode(TaskNode):
    """Analyze retrieval and answer metrics to surface failure modes."""

    recall_threshold: float = Field(
        default=0.6, description="Minimum acceptable recall before flagging failures."
    )
    faithfulness_threshold: float = Field(
        default=0.5, description="Minimum acceptable faithfulness for answers."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Flag failures when retrieval or answer quality falls below thresholds."""
        metrics = state.get("inputs", {}).get("metrics") or {}
        if not isinstance(metrics, dict):
            msg = "FailureAnalysisNode requires metrics dictionary"
            raise ValueError(msg)

        failures: list[str] = []
        retrieval_metrics = metrics.get("retrieval", {})
        answer_metrics = metrics.get("answer", {})

        recall = float(retrieval_metrics.get("recall@k", 0.0))
        faithfulness = float(answer_metrics.get("faithfulness", 0.0))

        if recall < self.recall_threshold:
            failures.append("retrieval_failure")
        if faithfulness < self.faithfulness_threshold:
            failures.append("answer_quality_failure")
        if metrics.get("llm_verdict") == "fail":
            failures.append("llm_judge_failure")

        return {
            "failures": failures,
            "passed": not failures,
            "details": {
                "recall": recall,
                "faithfulness": faithfulness,
                "total_failures": len(failures),
            },
        }


@registry.register(
    NodeMetadata(
        name="ABTestingNode",
        description="Compare experiment variants using a target metric.",
        category="conversational_search",
    )
)
class ABTestingNode(TaskNode):
    """Select experiment winner based on a numeric metric."""

    metric_name: str = Field(
        default="score", description="Metric used to compare experiment variants."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Select the experiment variant with the best configured metric."""
        variants = state.get("inputs", {}).get("variants")
        if not isinstance(variants, dict) or not variants:
            msg = "ABTestingNode requires a variants mapping"
            raise ValueError(msg)

        best_variant = None
        best_score = float("-inf")

        for name, payload in variants.items():
            if not isinstance(payload, dict):
                msg = "Variant payloads must be dictionaries"
                raise ValueError(msg)
            score = float(payload.get(self.metric_name, float("-inf")))
            if score > best_score:
                best_score = score
                best_variant = name

        return {
            "winner": best_variant,
            "score": best_score,
            "variants_compared": len(variants),
        }


@registry.register(
    NodeMetadata(
        name="UserFeedbackCollectionNode",
        description="Normalize and validate user feedback signals.",
        category="conversational_search",
    )
)
class UserFeedbackCollectionNode(TaskNode):
    """Collect and standardize user feedback entries."""

    feedback_key: str = Field(
        default="feedback", description="Key containing raw feedback entries."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Validate user feedback entries and normalize structure."""
        feedback_entries = state.get("inputs", {}).get(self.feedback_key)
        if not isinstance(feedback_entries, list) or not feedback_entries:
            msg = "UserFeedbackCollectionNode requires a list of feedback entries"
            raise ValueError(msg)

        normalized: list[dict[str, Any]] = []
        for entry in feedback_entries:
            if not isinstance(entry, dict):
                msg = "Feedback entries must be dictionaries"
                raise ValueError(msg)
            rating = int(entry.get("rating", 0))
            if rating < 1 or rating > 5:
                msg = "rating must be between 1 and 5"
                raise ValueError(msg)
            normalized.append(
                {
                    "user": entry.get("user", "anonymous"),
                    "rating": rating,
                    "comment": entry.get("comment", "").strip(),
                    "query": entry.get("query", "").strip(),
                    "timestamp": entry.get("timestamp", time.time()),
                }
            )

        return {"feedback": normalized, "count": len(normalized)}


@registry.register(
    NodeMetadata(
        name="FeedbackIngestionNode",
        description="Merge feedback into an in-memory buffer for downstream use.",
        category="conversational_search",
    )
)
class FeedbackIngestionNode(TaskNode):
    """Persist feedback entries into a provided buffer."""

    existing_feedback: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Default buffer to merge feedback into when state does not provide one."
        ),
    )
    feedback_key: str = Field(
        default="feedback", description="Key for feedback entries to ingest."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Merge collected feedback into the configured buffer."""
        incoming_feedback = state.get("inputs", {}).get(self.feedback_key)
        if not isinstance(incoming_feedback, list) or not incoming_feedback:
            msg = "FeedbackIngestionNode requires feedback entries"
            raise ValueError(msg)

        combined = [*self.existing_feedback, *incoming_feedback]
        return {"feedback_store": combined, "total": len(combined)}


@registry.register(
    NodeMetadata(
        name="AnalyticsExportNode",
        description="Export metrics and feedback in a consolidated payload.",
        category="conversational_search",
    )
)
class AnalyticsExportNode(TaskNode):
    """Package analytics results for downstream sinks."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Combine metrics and feedback into a consolidated export payload."""
        metrics = state.get("inputs", {}).get("metrics") or {}
        feedback = state.get("inputs", {}).get("feedback") or []
        if not isinstance(metrics, dict):
            msg = "AnalyticsExportNode requires metrics dictionary"
            raise ValueError(msg)
        if not isinstance(feedback, list):
            msg = "AnalyticsExportNode requires feedback list"
            raise ValueError(msg)

        return {
            "export": {
                "metrics": metrics,
                "feedback": feedback,
                "generated_at": time.time(),
            },
            "feedback_count": len(feedback),
        }


@registry.register(
    NodeMetadata(
        name="PolicyComplianceNode",
        description="Apply simple policy checks with audit logging.",
        category="conversational_search",
    )
)
class PolicyComplianceNode(TaskNode):
    """Run lightweight compliance checks on content."""

    content_key: str = Field(
        default="content",
        description="Key within ``state.inputs`` containing content to scan.",
    )
    banned_terms: set[str] = Field(
        default_factory=lambda: {"ssn", "credit card", "password"},
        description="Terms that trigger policy violations.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Check content for banned terms and record an audit log."""
        content = str(state.get("inputs", {}).get(self.content_key, "")).lower()
        if not content.strip():
            msg = "PolicyComplianceNode requires content to inspect"
            raise ValueError(msg)

        violations = [term for term in self.banned_terms if term in content]
        audit_log = {
            "timestamp": time.time(),
            "checked_terms": sorted(self.banned_terms),
            "violations": violations,
        }

        return {
            "passed": not violations,
            "violations": violations,
            "audit_log": audit_log,
        }


@registry.register(
    NodeMetadata(
        name="MemoryPrivacyNode",
        description="Redact sensitive metadata and enforce retention for stored turns.",
        category="conversational_search",
    )
)
class MemoryPrivacyNode(TaskNode):
    """Apply privacy controls to conversation history."""

    history_key: str = Field(
        default="history", description="Key containing conversation turns to sanitize."
    )
    redacted_metadata_keys: set[str] = Field(
        default_factory=lambda: {"email", "ssn", "phone"},
        description="Metadata keys that should be removed from turns.",
    )
    max_turns: int | None = Field(
        default=10, description="Maximum number of turns to retain after sanitization."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Remove sensitive metadata keys and trim the retained history length."""
        history = state.get("inputs", {}).get(self.history_key)
        if not isinstance(history, list) or not history:
            msg = "MemoryPrivacyNode requires a list of conversation turns"
            raise ValueError(msg)

        sanitized: list[dict[str, Any]] = []
        for turn in history:
            if not isinstance(turn, dict):
                msg = "Conversation turns must be dictionaries"
                raise ValueError(msg)
            metadata = {
                key: value
                for key, value in (turn.get("metadata") or {}).items()
                if key not in self.redacted_metadata_keys
            }
            sanitized.append({**turn, "metadata": metadata})

        if self.max_turns is not None and self.max_turns > 0:
            sanitized = sanitized[-self.max_turns :]

        audit_log = {
            "timestamp": time.time(),
            "removed_keys": sorted(self.redacted_metadata_keys),
            "remaining_turns": len(sanitized),
        }

        return {"history": sanitized, "audit_log": audit_log}


@registry.register(
    NodeMetadata(
        name="DataAugmentationNode",
        description="Generate synthetic dataset variants for robustness.",
        category="conversational_search",
    )
)
class DataAugmentationNode(TaskNode):
    """Create lightweight paraphrases for evaluation datasets."""

    dataset_key: str = Field(
        default="dataset", description="Key containing dataset entries to augment."
    )
    augmentations_per_example: int = Field(
        default=1, ge=0, le=3, description="Number of augmentations per dataset entry."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Create lightweight synthetic variations of dataset entries."""
        dataset = state.get("inputs", {}).get(self.dataset_key)
        if not isinstance(dataset, list) or not dataset:
            msg = "DataAugmentationNode requires dataset entries"
            raise ValueError(msg)

        augmented: list[dict[str, Any]] = []
        for entry in dataset:
            if not isinstance(entry, dict):
                msg = "Dataset entries must be dictionaries"
                raise ValueError(msg)
            augmented.append(entry)
            for index in range(self.augmentations_per_example):
                augmented_example = dict(entry)
                augmented_example["query"] = (
                    f"{entry.get('query', '')} (augmented {index + 1})"
                )
                augmented_example["augmentation"] = True
                augmented.append(augmented_example)

        return {"augmented_dataset": augmented, "total": len(augmented)}


@registry.register(
    NodeMetadata(
        name="TurnAnnotationNode",
        description="Annotate conversation turns with lightweight labels.",
        category="conversational_search",
    )
)
class TurnAnnotationNode(TaskNode):
    """Add intent and topic annotations to conversation turns."""

    history_key: str = Field(
        default="history", description="Key containing raw conversation turns."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Label turns with coarse intent and topic annotations."""
        history = state.get("inputs", {}).get(self.history_key)
        if not isinstance(history, list) or not history:
            msg = "TurnAnnotationNode requires conversation turns"
            raise ValueError(msg)

        annotated: list[dict[str, Any]] = []
        for turn in history:
            if not isinstance(turn, dict):
                msg = "Conversation turns must be dictionaries"
                raise ValueError(msg)
            content = str(turn.get("content", ""))
            intent = "question" if "?" in content else "statement"
            topic = "feedback" if "feedback" in content.lower() else "information"
            annotated.append({**turn, "intent": intent, "topic": topic})

        return {"annotated_history": annotated, "count": len(annotated)}
