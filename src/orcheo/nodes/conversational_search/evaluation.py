"""Evaluation, analytics, and compliance nodes for conversational search."""

from __future__ import annotations
import inspect
import math
import re
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import (
    ComplianceFinding,
    EvaluationExample,
    FeedbackRecord,
    SearchResult,
)
from orcheo.nodes.registry import NodeMetadata, registry


def _ensure_list(payload: Any, error: str) -> list[Any]:
    if not isinstance(payload, list):
        msg = error
        raise ValueError(msg)
    return payload


@registry.register(
    NodeMetadata(
        name="DatasetNode",
        description="Load evaluation dataset examples for downstream scoring.",
        category="conversational_search",
    )
)
class DatasetNode(TaskNode):
    """Node that materializes evaluation examples."""

    dataset: list[EvaluationExample | dict[str, Any]] = Field(
        default_factory=list,
        description="Static dataset payload used when inputs do not provide one.",
    )
    dataset_loader: Callable[[], list[EvaluationExample | dict[str, Any]]] | None = (
        Field(
            default=None,
            description="Optional callable returning dataset records (sync or async).",
        )
    )
    dataset_key: str = Field(
        default="dataset",
        description="Key in state inputs/results containing dataset overrides.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a validated dataset ready for evaluation nodes."""
        del config
        examples = await self._load_dataset(state)
        normalized = [EvaluationExample.model_validate(example) for example in examples]
        return {"dataset": normalized}

    async def _load_dataset(
        self, state: State
    ) -> list[EvaluationExample | dict[str, Any]]:
        from_state = state.get("inputs", {}).get(self.dataset_key) or state.get(
            "results", {}
        ).get(self.dataset_key)
        if from_state is not None:
            return _ensure_list(
                from_state, "Provided dataset must be a list of examples"
            )

        if self.dataset_loader is not None:
            output = self.dataset_loader()
            if inspect.isawaitable(output):
                output = await output  # type: ignore[assignment]
            return _ensure_list(output, "Dataset loader must return a list of examples")

        if not self.dataset:
            msg = "DatasetNode requires a dataset via loader, inputs, or configuration"
            raise ValueError(msg)
        return self.dataset


def _normalize_dataset(state: State, key: str) -> list[EvaluationExample]:
    dataset = state.get("results", {}).get(key) or state.get("inputs", {}).get(key)
    if dataset is None:
        msg = f"Dataset with key '{key}' was not found in state"
        raise ValueError(msg)
    examples = _ensure_list(dataset, "dataset must be a list")
    return [EvaluationExample.model_validate(example) for example in examples]


def _normalize_mapping(value: Any, error: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    msg = error
    raise ValueError(msg)


@registry.register(
    NodeMetadata(
        name="RetrievalEvaluationNode",
        description="Compute retrieval metrics such as Recall@k, MRR, and NDCG.",
        category="conversational_search",
    )
)
class RetrievalEvaluationNode(TaskNode):
    """Node that evaluates retrieval quality against ground truth labels."""

    dataset_key: str = Field(
        default="dataset", description="Key holding normalized evaluation examples"
    )
    retrieval_result_key: str = Field(
        default="retrieval_results",
        description="Key in state.results containing retrieval outputs.",
    )
    results_field: str = Field(
        default="results",
        description="Field containing list of :class:`SearchResult` instances",
    )
    top_k: int = Field(default=5, gt=0, description="Number of results considered")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compute aggregate retrieval metrics across provided examples."""
        del config
        dataset = _normalize_dataset(state, self.dataset_key)
        retrieval_payload = state.get("results", {}).get(self.retrieval_result_key)
        if retrieval_payload is None:
            retrieval_payload = state.get("results", {}).get(self.results_field)
        mapping = self._normalize_retrieval_map(retrieval_payload, dataset)
        per_example: dict[str, dict[str, float]] = {}

        recalls: list[float] = []
        mrrs: list[float] = []
        ndcgs: list[float] = []
        maps: list[float] = []

        for example in dataset:
            retrieved = mapping.get(example.id, [])
            metrics = self._score_example(example, retrieved)
            per_example[example.id] = metrics
            recalls.append(metrics["recall"])
            mrrs.append(metrics["mrr"])
            ndcgs.append(metrics["ndcg"])
            maps.append(metrics["map"])

        aggregated = {
            "recall": sum(recalls) / len(recalls) if recalls else 0.0,
            "mrr": sum(mrrs) / len(mrrs) if mrrs else 0.0,
            "ndcg": sum(ndcgs) / len(ndcgs) if ndcgs else 0.0,
            "map": sum(maps) / len(maps) if maps else 0.0,
        }
        return {
            "retrieval_metrics": aggregated,
            "per_example": per_example,
        }

    def _normalize_retrieval_map(
        self, payload: Any, dataset: list[EvaluationExample]
    ) -> dict[str, list[SearchResult]]:
        if payload is None:
            msg = "Retrieval results were not provided in state"
            raise ValueError(msg)
        if isinstance(payload, list):
            if len(dataset) != 1:
                msg = "List retrieval payload requires a single dataset example"
                raise ValueError(msg)
            payload = {dataset[0].id: payload}
        mapping = _normalize_mapping(
            payload, "Retrieval results must be a dict keyed by example id"
        )
        normalized: dict[str, list[SearchResult]] = {}
        for example_id, results in mapping.items():
            normalized[example_id] = [
                SearchResult.model_validate(result)
                for result in _ensure_list(
                    results, "Retrieval results for each example must be a list"
                )
            ][: self.top_k]
        return normalized

    def _score_example(
        self, example: EvaluationExample, results: list[SearchResult]
    ) -> dict[str, float]:
        relevant = example.relevant_ids
        if not relevant:
            return {"recall": 1.0, "mrr": 1.0, "ndcg": 1.0, "map": 1.0}

        gains = []
        hits = 0
        dcg = 0.0
        avg_precision = 0.0
        reciprocal_rank = 0.0
        for idx, result in enumerate(results, start=1):
            hit = result.id in relevant
            gains.append(1.0 if hit else 0.0)
            if hit:
                hits += 1
                if reciprocal_rank == 0.0:
                    reciprocal_rank = 1.0 / idx
                precision_at_k = hits / idx
                avg_precision += precision_at_k
                dcg += 1.0 / math.log2(idx + 1)

        recall = hits / len(relevant)
        ideal_cutoff = min(len(results), len(relevant))
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_cutoff))
        ndcg = dcg / idcg if idcg else 0.0
        mean_avg_precision = avg_precision / len(relevant)

        return {
            "recall": recall,
            "mrr": reciprocal_rank,
            "ndcg": ndcg,
            "map": mean_avg_precision,
        }


@registry.register(
    NodeMetadata(
        name="AnswerQualityEvaluationNode",
        description="Compute lexical quality metrics such as F1 and exact match.",
        category="conversational_search",
    )
)
class AnswerQualityEvaluationNode(TaskNode):
    """Node that compares generated answers against reference labels."""

    dataset_key: str = Field(default="dataset")
    answers_key: str = Field(
        default="answers",
        description="Key containing a mapping of example id to generated answer",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score answers against reference text using lexical metrics."""
        del config
        dataset = _normalize_dataset(state, self.dataset_key)
        answers_payload = state.get("results", {}).get(self.answers_key) or state.get(
            "inputs", {}
        ).get(self.answers_key)
        answers = _normalize_mapping(
            answers_payload, "answers payload must be a dict keyed by example id"
        )

        per_example: dict[str, dict[str, float | bool]] = {}
        f1_scores: list[float] = []
        em_scores: list[float] = []
        for example in dataset:
            reference = example.reference_answer or ""
            predicted = str(answers.get(example.id, ""))
            f1 = self._f1(reference, predicted)
            exact_match = reference.strip().lower() == predicted.strip().lower()
            per_example[example.id] = {
                "f1": f1,
                "exact_match": exact_match,
            }
            f1_scores.append(f1)
            em_scores.append(1.0 if exact_match else 0.0)

        metrics = {
            "average_f1": sum(f1_scores) / len(f1_scores) if f1_scores else 0.0,
            "exact_match_rate": sum(em_scores) / len(em_scores) if em_scores else 0.0,
        }
        return {
            "answer_quality": metrics,
            "per_example": per_example,
        }

    def _f1(self, reference: str, predicted: str) -> float:
        ref_tokens = reference.lower().split()
        pred_tokens = predicted.lower().split()
        if not ref_tokens and not pred_tokens:
            return 1.0
        if not ref_tokens or not pred_tokens:
            return 0.0
        ref_counts: dict[str, int] = defaultdict(int)
        for token in ref_tokens:
            ref_counts[token] += 1
        common = 0
        for token in pred_tokens:
            if ref_counts[token] > 0:
                common += 1
                ref_counts[token] -= 1
        precision = common / len(pred_tokens)
        recall = common / len(ref_tokens)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)


@registry.register(
    NodeMetadata(
        name="LLMJudgeNode",
        description="Use an LLM or heuristic judge to score generated answers.",
        category="conversational_search",
    )
)
class LLMJudgeNode(TaskNode):
    """Node that assigns quality scores using a pluggable judge function."""

    dataset_key: str = Field(default="dataset")
    answers_key: str = Field(default="answers")
    judge: Callable[[str, EvaluationExample], float | dict[str, Any]] | None = Field(  # type: ignore[misc]
        default=None,
        description="Callable returning a numeric score or structured judgement.",
    )
    passing_threshold: float = Field(
        default=0.6, description="Minimum score considered acceptable"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the judge function for each answer and aggregate results."""
        del config
        dataset = _normalize_dataset(state, self.dataset_key)
        answers_payload = state.get("results", {}).get(self.answers_key)
        answers = _normalize_mapping(
            answers_payload, "LLMJudgeNode requires answers keyed by example id"
        )

        per_example: dict[str, dict[str, Any]] = {}
        scores: list[float] = []
        for example in dataset:
            answer = str(answers.get(example.id, ""))
            judgement = await self._score_answer(answer, example)
            if isinstance(judgement, dict):
                score = float(judgement.get("score", 0.0))
                rationale = judgement.get("rationale", "")
            else:
                score = float(judgement)
                rationale = ""
            per_example[example.id] = {
                "score": score,
                "pass": score >= self.passing_threshold,
                "rationale": rationale,
            }
            scores.append(score)

        return {
            "judge_scores": per_example,
            "average_score": sum(scores) / len(scores) if scores else 0.0,
        }

    async def _score_answer(
        self, answer: str, example: EvaluationExample
    ) -> float | dict[str, Any]:
        judge_fn = self.judge or self._default_judge
        output = judge_fn(answer, example)
        if inspect.isawaitable(output):
            output = await output  # type: ignore[assignment]
        return output

    def _default_judge(self, answer: str, example: EvaluationExample) -> float:
        reference = example.reference_answer or ""
        if not reference:
            return 0.5
        overlap = len(set(answer.lower().split()) & set(reference.lower().split()))
        return min(1.0, 0.2 + overlap / max(len(reference.split()), 1))


@registry.register(
    NodeMetadata(
        name="FailureAnalysisNode",
        description="Categorize failures across retrieval and generation metrics.",
        category="conversational_search",
    )
)
class FailureAnalysisNode(TaskNode):
    """Node that surfaces likely failure modes with actionable tags."""

    retrieval_metrics_key: str = Field(default="retrieval_metrics")
    answer_metrics_key: str = Field(default="answer_quality")
    judge_scores_key: str = Field(default="average_score")
    min_recall: float = Field(default=0.5, ge=0.0, le=1.0)
    min_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    min_judge: float = Field(default=0.6, ge=0.0, le=1.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Summarize failures using thresholds for retrieval and quality."""
        del config
        retrieval_metrics = _normalize_mapping(
            state.get("results", {}).get(self.retrieval_metrics_key),
            "FailureAnalysisNode requires retrieval metrics",
        )
        answer_metrics = _normalize_mapping(
            state.get("results", {}).get(self.answer_metrics_key),
            "FailureAnalysisNode requires answer quality metrics",
        )
        judge_score = state.get("results", {}).get(self.judge_scores_key, 0.0)

        findings: list[str] = []
        if retrieval_metrics.get("recall", 0.0) < self.min_recall:
            findings.append("retrieval_recall_low")
        if retrieval_metrics.get("ndcg", 0.0) < self.min_recall:
            findings.append("retrieval_ranking_weak")
        if answer_metrics.get("average_f1", 0.0) < self.min_quality:
            findings.append("generation_quality_low")
        if answer_metrics.get("exact_match_rate", 0.0) < self.min_quality:
            findings.append("ground_truth_mismatch")
        if judge_score < self.min_judge:
            findings.append("judge_confidence_low")

        status = "pass" if not findings else "action_required"
        return {"status": status, "findings": findings}


@registry.register(
    NodeMetadata(
        name="ABTestingNode",
        description="Compare two variants using a primary metric and choose a winner.",
        category="conversational_search",
    )
)
class ABTestingNode(TaskNode):
    """Node that selects a winning variant based on metric comparisons."""

    variant_a_key: str = Field(default="variant_a")
    variant_b_key: str = Field(default="variant_b")
    metric_key: str = Field(
        default="average_f1",
        description="Metric name used to determine the winner",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compare two metric dictionaries and declare a winner."""
        del config
        results = state.get("results", {})
        variant_a = _normalize_mapping(
            results.get(self.variant_a_key), "Variant A metrics must be a dict"
        )
        variant_b = _normalize_mapping(
            results.get(self.variant_b_key), "Variant B metrics must be a dict"
        )
        score_a = float(variant_a.get(self.metric_key, 0.0))
        score_b = float(variant_b.get(self.metric_key, 0.0))
        winner = "a" if score_a >= score_b else "b"
        return {
            "winner": winner,
            "score_delta": abs(score_a - score_b),
            "scores": {"a": score_a, "b": score_b},
        }


@registry.register(
    NodeMetadata(
        name="UserFeedbackCollectionNode",
        description="Collect user feedback entries for analytics and evaluation.",
        category="conversational_search",
    )
)
class UserFeedbackCollectionNode(TaskNode):
    """Node that normalizes user feedback payloads."""

    feedback_key: str = Field(default="feedback")
    rating_scale_max: int = Field(default=5, gt=0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Normalize and validate user feedback payloads."""
        del config
        payload = state.get("inputs", {}).get(self.feedback_key) or state.get(
            "results", {}
        ).get(self.feedback_key)
        records = _ensure_list(payload or [], "feedback payload must be a list")
        normalized: list[FeedbackRecord] = []
        timestamp = time.time()
        for record in records:
            feedback = FeedbackRecord.model_validate(record)
            if feedback.rating > self.rating_scale_max:
                msg = "feedback rating exceeds configured maximum"
                raise ValueError(msg)
            if feedback.timestamp is None:
                feedback.timestamp = timestamp
            normalized.append(feedback)
        return {"feedback": normalized}


@registry.register(
    NodeMetadata(
        name="FeedbackIngestionNode",
        description="Attach collected feedback to evaluation examples for tracing.",
        category="conversational_search",
    )
)
class FeedbackIngestionNode(TaskNode):
    """Node that merges feedback signals into dataset metadata."""

    dataset_key: str = Field(default="dataset")
    feedback_key: str = Field(default="feedback")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Attach collected feedback to each dataset example."""
        del config
        dataset = _normalize_dataset(state, self.dataset_key)
        feedback_payload = state.get("results", {}).get(self.feedback_key) or []
        feedback = _ensure_list(feedback_payload, "feedback must be provided as a list")
        ingested = []
        for example in dataset:
            enriched = example.model_copy(deep=True)
            enriched.metadata["user_feedback"] = feedback
            ingested.append(enriched)
        return {"dataset": ingested, "ingested_feedback": len(feedback)}


@registry.register(
    NodeMetadata(
        name="AnalyticsExportNode",
        description="Export metrics and feedback to an external sink.",
        category="conversational_search",
    )
)
class AnalyticsExportNode(TaskNode):
    """Node that aggregates evaluation results into a report."""

    retrieval_metrics_key: str = Field(default="retrieval_metrics")
    answer_metrics_key: str = Field(default="answer_quality")
    judge_scores_key: str = Field(default="average_score")
    feedback_key: str = Field(default="feedback")
    sink: Callable[[dict[str, Any]], Any] | None = Field(
        default=None,
        description="Optional callable to receive the generated report.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Build an analytics report and optionally export it."""
        del config
        results = state.get("results", {})
        report = {
            "retrieval": _normalize_mapping(
                results.get(self.retrieval_metrics_key),
                "retrieval metrics missing",
            ),
            "answers": _normalize_mapping(
                results.get(self.answer_metrics_key), "answer metrics missing"
            ),
            "judge": results.get(self.judge_scores_key, 0.0),
            "feedback": results.get(self.feedback_key, []),
        }
        exported = False
        if self.sink:
            output = self.sink(report)
            if inspect.isawaitable(output):
                await output  # type: ignore[func-returns-value]
            exported = True
        return {"report": report, "exported": exported}


@registry.register(
    NodeMetadata(
        name="PolicyComplianceNode",
        description="Check responses for policy or compliance violations.",
        category="conversational_search",
    )
)
class PolicyComplianceNode(TaskNode):
    """Node that flags policy violations in answers or retrieved context."""

    answer_key: str = Field(default="answers")
    banned_terms: list[str] = Field(
        default_factory=lambda: ["ssn", "password", "secret"],
        description="Terms that should not appear in answers",
    )
    severity: str = Field(default="critical")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Flag banned terms in answers for compliance review."""
        del config
        answers_payload = state.get("results", {}).get(self.answer_key) or {}
        answers = _normalize_mapping(
            answers_payload, "PolicyComplianceNode requires answers dictionary"
        )
        findings: list[ComplianceFinding] = []
        for example_id, answer in answers.items():
            text = str(answer).lower()
            for term in self.banned_terms:
                if term.lower() in text:
                    findings.append(
                        ComplianceFinding(
                            policy="banned_term",
                            message=(
                                f"Example {example_id} contains banned term '{term}'"
                            ),
                            severity=self.severity,
                        )
                    )
        return {"findings": findings, "compliant": not findings}


@registry.register(
    NodeMetadata(
        name="MemoryPrivacyNode",
        description="Redact sensitive fields from memory state for privacy compliance.",
        category="conversational_search",
    )
)
class MemoryPrivacyNode(TaskNode):
    """Node that sanitizes memory entries for PII and sensitive keys."""

    memory_key: str = Field(default="memory")
    sensitive_fields: list[str] = Field(
        default_factory=lambda: ["email", "ssn", "phone"],
        description="Field names to redact from memory entries",
    )
    redaction_token: str = Field(default="[REDACTED]")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Redact sensitive fields and basic PII from memory entries."""
        del config
        memory_payload = state.get("results", {}).get(self.memory_key) or state.get(
            "inputs", {}
        ).get(self.memory_key)
        entries = _ensure_list(memory_payload or [], "memory must be a list of dicts")
        sanitized: list[dict[str, Any]] = []
        redacted = 0
        pii_pattern = re.compile(r"(\d{3}-\d{2}-\d{4}|\d{10})")
        for entry in entries:
            if not isinstance(entry, dict):
                msg = "memory entries must be dictionaries"
                raise ValueError(msg)
            clean = {}
            for key, value in entry.items():
                if key.lower() in self.sensitive_fields:
                    clean[key] = self.redaction_token
                    redacted += 1
                    continue
                if isinstance(value, str) and pii_pattern.search(value):
                    clean[key] = pii_pattern.sub(self.redaction_token, value)
                    redacted += 1
                else:
                    clean[key] = value
            sanitized.append(clean)
        return {"sanitized_memory": sanitized, "redacted_count": redacted}


@registry.register(
    NodeMetadata(
        name="DataAugmentationNode",
        description="Generate augmented dataset entries for robustness.",
        category="conversational_search",
    )
)
class DataAugmentationNode(TaskNode):
    """Node that creates synthetic variations of evaluation examples."""

    dataset_key: str = Field(default="dataset")
    augmentation_count: int = Field(default=1, ge=0)
    prefix: str = Field(default="aug")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate deterministic augmented examples for the dataset."""
        del config
        dataset = _normalize_dataset(state, self.dataset_key)
        augmented: list[EvaluationExample] = list(dataset)
        for example in dataset:
            for idx in range(self.augmentation_count):
                augmented.append(
                    EvaluationExample(
                        id=f"{example.id}-{self.prefix}-{idx}",
                        query=f"{example.query} ({self.prefix} {idx})",
                        relevant_ids=list(example.relevant_ids),
                        reference_answer=example.reference_answer,
                        metadata={**example.metadata, "augmented": True},
                    )
                )
        return {
            "augmented_dataset": augmented,
            "augmentation_count": max(0, len(augmented) - len(dataset)),
        }


@registry.register(
    NodeMetadata(
        name="TurnAnnotationNode",
        description="Annotate conversation turns with lightweight signals.",
        category="conversational_search",
    )
)
class TurnAnnotationNode(TaskNode):
    """Node that adds semantic annotations to conversation turns."""

    conversation_key: str = Field(default="conversation")
    annotation_field: str = Field(default="annotations")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Annotate conversation turns with simple heuristics."""
        del config
        conversation = state.get("inputs", {}).get(self.conversation_key) or state.get(
            "results", {}
        ).get(self.conversation_key)
        turns = _ensure_list(
            conversation or [], "conversation must be provided as a list of turns"
        )
        annotated_turns: list[dict[str, Any]] = []
        for turn in turns:
            if not isinstance(turn, dict) or "content" not in turn:
                msg = "each conversation turn must be a dict with 'content'"
                raise ValueError(msg)
            content = str(turn.get("content", ""))
            annotations = {
                "is_question": content.strip().endswith("?"),
                "sentiment": self._sentiment(content),
                "length": len(content.split()),
            }
            annotated_turns.append({**turn, self.annotation_field: annotations})
        return {"conversation": annotated_turns}

    def _sentiment(self, content: str) -> str:
        lowered = content.lower()
        if any(word in lowered for word in ["thanks", "great", "appreciate"]):
            return "positive"
        if any(word in lowered for word in ["bad", "terrible", "upset"]):
            return "negative"
        return "neutral"
