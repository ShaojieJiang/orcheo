"""Evaluation, analytics, and compliance nodes for conversational search."""

from __future__ import annotations
import math
import re
from collections import Counter
from datetime import datetime
from re import Pattern
from statistics import mean
from typing import Any, ClassVar, TypedDict
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


class DatasetRecord(BaseModel):
    """Structured entry for evaluation datasets."""

    query: str = Field(description="User query text used for evaluation")
    relevant_ids: list[str] = Field(
        default_factory=list,
        description="Identifiers for documents considered relevant to the query",
    )
    reference_answer: str | None = Field(
        default=None, description="Optional reference answer for answer quality"
    )
    context: list[str] = Field(
        default_factory=list, description="Optional supporting context passages"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        if not value or not value.strip():
            msg = "DatasetRecord.query must be a non-empty string"
            raise ValueError(msg)
        return value.strip()


class AnswerRecord(BaseModel):
    """Generated answer paired with its originating query."""

    query: str = Field(description="Query that produced the answer")
    answer: str = Field(description="Model-generated answer text")
    citations: list[str] = Field(
        default_factory=list, description="Optional citations or source hints"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("answer")
    @classmethod
    def _validate_answer(cls, value: str) -> str:
        if not value.strip():
            msg = "Answer text cannot be empty"
            raise ValueError(msg)
        return value.strip()


class AnswerEvaluationMetrics(TypedDict):
    """Structured answer evaluation payload."""

    overlap: float
    faithfulness: float
    exact_match: bool


def _resolve_payload(state: State, result_key: str, field_name: str) -> Any:
    results = state.get("results", {}) if isinstance(state, dict) else {}
    payload = results.get(result_key)
    if isinstance(payload, dict) and field_name in payload:
        return payload[field_name]
    return results.get(field_name)


@registry.register(
    NodeMetadata(
        name="DatasetNode",
        description="Load and validate evaluation datasets with relevance labels.",
        category="conversational_search",
    )
)
class DatasetNode(TaskNode):
    """Node that surfaces structured evaluation datasets."""

    dataset: list[DatasetRecord] | None = Field(
        default=None, description="Inline dataset records"
    )
    dataset_input_key: str = Field(
        default="dataset",
        description="Input key containing dataset records when not provided inline",
    )
    name: str = Field(default="dataset")
    version: str = Field(default="v1")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return validated dataset records and metadata."""
        raw = self.dataset
        if raw is None:
            inputs = state.get("inputs", {})
            candidate = inputs.get(self.dataset_input_key)
            if candidate is None:
                msg = (
                    "DatasetNode requires either inline dataset or "
                    "inputs[dataset_input_key]"
                )
                raise ValueError(msg)
            raw = candidate

        if not isinstance(raw, list):
            msg = "Dataset payload must be a list of records"
            raise ValueError(msg)

        records = [DatasetRecord.model_validate(item) for item in raw]
        metadata = {"version": self.version, "size": len(records), "name": self.name}
        return {"dataset": records, "metadata": metadata}


@registry.register(
    NodeMetadata(
        name="RetrievalEvaluationNode",
        description="Compute retrieval metrics such as Recall@k, MRR, NDCG, and MAP.",
        category="conversational_search",
    )
)
class RetrievalEvaluationNode(TaskNode):
    """Evaluate retrieval quality against a labeled dataset."""

    dataset_result_key: str = Field(
        default="dataset", description="Result key containing DatasetNode output"
    )
    dataset_field: str = Field(default="dataset")
    retrieval_result_key: str = Field(
        default="retrieval_results",
        description="Result key containing retrieval outputs",
    )
    retrieval_field: str = Field(
        default="results", description="Field containing retrieval results"
    )
    k: int = Field(default=5, gt=0, description="Cutoff for recall@k and NDCG")
    score_field: str = Field(
        default="score", description="Field name for retrieval scores"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compute aggregate retrieval metrics for labeled datasets."""
        dataset_payload = _resolve_payload(
            state, self.dataset_result_key, self.dataset_field
        )
        retrieval_payload = _resolve_payload(
            state, self.retrieval_result_key, self.retrieval_field
        )

        if not isinstance(dataset_payload, list):
            msg = "RetrievalEvaluationNode requires a list of dataset records"
            raise ValueError(msg)
        if not isinstance(retrieval_payload, list):
            msg = "RetrievalEvaluationNode requires a list of retrieval results"
            raise ValueError(msg)

        dataset = [DatasetRecord.model_validate(item) for item in dataset_payload]
        retrieval_index = self._build_retrieval_index(retrieval_payload)

        per_query = []
        recalls: list[float] = []
        mrrs: list[float] = []
        ndcgs: list[float] = []
        maps: list[float] = []

        for record in dataset:
            retrieved = retrieval_index.get(record.query) or retrieval_index.get("", [])
            retrieved = retrieved[: self.k]
            metrics = self._compute_metrics(record, retrieved)
            per_query.append({"query": record.query, **metrics})
            recalls.append(metrics["recall_at_k"])
            mrrs.append(metrics["mrr"])
            ndcgs.append(metrics["ndcg"])
            maps.append(metrics["map"])

        summary = {
            "recall_at_k": mean(recalls) if recalls else 0.0,
            "mrr": mean(mrrs) if mrrs else 0.0,
            "ndcg": mean(ndcgs) if ndcgs else 0.0,
            "map": mean(maps) if maps else 0.0,
            "evaluated": len(per_query),
        }
        return {"metrics": summary, "per_query": per_query}

    def _build_retrieval_index(
        self, payload: list[Any]
    ) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}
        for entry in payload:
            if isinstance(entry, dict) and "query" in entry:
                results = entry.get(self.retrieval_field, entry.get("results", []))
                index[entry["query"]] = self._normalize_results(results)
            else:
                # Single query mode
                index.setdefault("", self._normalize_results(payload))
                break
        return index

    def _normalize_results(self, results: Any) -> list[dict[str, Any]]:
        if results is None:
            return []
        if not isinstance(results, list):
            msg = "Retrieval results must be a list"
            raise ValueError(msg)
        normalized: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, dict):
                normalized.append(result)
        return normalized

    def _compute_metrics(
        self, record: DatasetRecord, retrieved: list[dict[str, Any]]
    ) -> dict[str, float]:
        relevant = [rid.lower() for rid in record.relevant_ids]
        if not relevant:
            return {"recall_at_k": 0.0, "mrr": 0.0, "ndcg": 0.0, "map": 0.0}

        hits = [
            idx
            for idx, item in enumerate(retrieved, start=1)
            if str(item.get("id", "")).lower() in relevant
        ]

        recall = len(hits) / len(relevant)
        mrr = 1 / hits[0] if hits else 0.0

        dcg = sum(1 / math.log2(rank + 1) for rank in hits)
        ideal_hits = list(range(1, min(len(relevant), self.k) + 1))
        idcg = sum(1 / math.log2(rank + 1) for rank in ideal_hits)
        ndcg = dcg / idcg if idcg > 0 else 0.0

        precisions = []
        for i, _ in enumerate(retrieved, start=1):
            top_i = retrieved[:i]
            tp = sum(1 for item in top_i if str(item.get("id", "")).lower() in relevant)
            precisions.append(tp / i)
        average_precision = sum(precisions[idx - 1] for idx in hits) / len(relevant)

        return {
            "recall_at_k": min(recall, 1.0),
            "mrr": mrr,
            "ndcg": ndcg,
            "map": average_precision,
        }


@registry.register(
    NodeMetadata(
        name="AnswerQualityEvaluationNode",
        description="Score generated answers against references and context.",
        category="conversational_search",
    )
)
class AnswerQualityEvaluationNode(TaskNode):
    """Evaluate answer quality using overlap and context grounding heuristics."""

    dataset_result_key: str = Field(default="dataset")
    dataset_field: str = Field(default="dataset")
    answers_result_key: str = Field(default="answers")
    answers_field: str = Field(default="answers")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score answers against references and supporting context."""
        dataset_payload = _resolve_payload(
            state, self.dataset_result_key, self.dataset_field
        )
        answers_payload = _resolve_payload(
            state, self.answers_result_key, self.answers_field
        )

        if not isinstance(dataset_payload, list):
            msg = "AnswerQualityEvaluationNode requires dataset records"
            raise ValueError(msg)
        if not isinstance(answers_payload, list):
            msg = "AnswerQualityEvaluationNode requires a list of answers"
            raise ValueError(msg)

        dataset = [DatasetRecord.model_validate(item) for item in dataset_payload]
        answers = [AnswerRecord.model_validate(item) for item in answers_payload]
        answer_lookup = {answer.query: answer for answer in answers}

        per_query = []
        faithfulness_scores: list[float] = []
        overlap_scores: list[float] = []
        exact_matches: list[bool] = []

        for record in dataset:
            answer = answer_lookup.get(record.query)
            if answer is None:
                continue
            metrics = self._score_answer(record, answer)
            per_query.append({"query": record.query, **metrics})
            faithfulness_scores.append(metrics["faithfulness"])
            overlap_scores.append(metrics["overlap"])
            exact_matches.append(metrics["exact_match"])

        summary = {
            "faithfulness": mean(faithfulness_scores) if faithfulness_scores else 0.0,
            "overlap": mean(overlap_scores) if overlap_scores else 0.0,
            "exact_match_rate": (
                sum(1 for match in exact_matches if match) / len(exact_matches)
            )
            if exact_matches
            else 0.0,
            "evaluated": len(per_query),
        }
        return {"metrics": summary, "per_query": per_query}

    def _score_answer(
        self, record: DatasetRecord, answer: AnswerRecord
    ) -> AnswerEvaluationMetrics:
        reference = (record.reference_answer or "").strip().lower()
        answer_text = answer.answer.strip().lower()

        reference_tokens = reference.split()
        answer_tokens = answer_text.split()
        overlap = 0.0
        if reference_tokens:
            overlap = len(set(reference_tokens) & set(answer_tokens)) / len(
                reference_tokens
            )

        context_tokens = " ".join(record.context).lower().split()
        grounded = (
            len(set(answer_tokens) & set(context_tokens)) / len(answer_tokens)
            if answer_tokens
            else 0.0
        )

        faithfulness = (
            (overlap + grounded) / 2 if reference_tokens or context_tokens else 0.5
        )
        exact_match = answer_text == reference if reference else False

        return AnswerEvaluationMetrics(
            overlap=overlap, faithfulness=faithfulness, exact_match=exact_match
        )


@registry.register(
    NodeMetadata(
        name="LLMJudgeNode",
        description="Rule-based evaluator that simulates LLM-as-a-judge scoring.",
        category="conversational_search",
    )
)
class LLMJudgeNode(TaskNode):
    """Deterministic judge for answers when offline LLM access is unavailable."""

    answers_result_key: str = Field(default="answers")
    answers_field: str = Field(default="answers")
    dataset_result_key: str = Field(default="dataset")
    dataset_field: str = Field(default="dataset")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Simulate LLM judging using deterministic heuristics."""
        answers_payload = _resolve_payload(
            state, self.answers_result_key, self.answers_field
        )
        dataset_payload = _resolve_payload(
            state, self.dataset_result_key, self.dataset_field
        )

        if not isinstance(answers_payload, list):
            msg = "LLMJudgeNode requires a list of answers"
            raise ValueError(msg)
        if not isinstance(dataset_payload, list):
            msg = "LLMJudgeNode requires dataset records"
            raise ValueError(msg)

        answers = [AnswerRecord.model_validate(item) for item in answers_payload]
        dataset = {
            item.query: item
            for item in [DatasetRecord.model_validate(item) for item in dataset_payload]
        }

        verdicts: list[dict[str, Any]] = []
        for answer in answers:
            record = dataset.get(answer.query)
            score, reasoning = self._score_answer(answer, record)
            verdicts.append(
                {
                    "query": answer.query,
                    "score": score,
                    "verdict": "pass" if score >= self.threshold else "fail",
                    "reason": reasoning,
                }
            )

        average_score = mean([item["score"] for item in verdicts]) if verdicts else 0.0
        return {"verdicts": verdicts, "average_score": average_score}

    def _score_answer(
        self, answer: AnswerRecord, record: DatasetRecord | None
    ) -> tuple[float, str]:
        reference = (record.reference_answer if record else "") or ""
        overlap = 0.0
        if reference:
            reference_tokens = reference.lower().split()
            overlap = len(
                set(reference_tokens) & set(answer.answer.lower().split())
            ) / len(reference_tokens)

        citation_bonus = 0.1 if answer.citations else 0.0
        brevity_penalty = 0.0
        if len(answer.answer.split()) > 120:
            brevity_penalty = 0.15

        score = max(0.0, min(1.0, overlap + citation_bonus - brevity_penalty))
        reason = (
            "High reference overlap" if overlap >= 0.5 else "Limited reference overlap"
        )
        if answer.citations:
            reason += "; citations present"
        if brevity_penalty:
            reason += "; response overly long"
        return score, reason


@registry.register(
    NodeMetadata(
        name="FailureAnalysisNode",
        description="Categorize evaluation failures for diagnostics.",
        category="conversational_search",
    )
)
class FailureAnalysisNode(TaskNode):
    """Analyze evaluation outputs to label failure modes."""

    retrieval_result_key: str = Field(default="retrieval_evaluation")
    answer_result_key: str = Field(default="answer_quality")
    judge_result_key: str = Field(default="llm_judge")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Label failure modes based on retrieval and answer quality."""
        retrieval = _resolve_payload(state, self.retrieval_result_key, "per_query")
        answers = _resolve_payload(state, self.answer_result_key, "per_query")
        verdicts = _resolve_payload(state, self.judge_result_key, "verdicts")

        failures: list[dict[str, Any]] = []
        verdict_lookup = {item.get("query"): item for item in verdicts or []}
        answer_lookup = {item.get("query"): item for item in answers or []}

        for entry in retrieval or []:
            query = entry.get("query")
            failure_modes = []
            if entry.get("recall_at_k", 1.0) < 0.5:
                failure_modes.append("low_recall")
            if entry.get("mrr", 1.0) < 0.25:
                failure_modes.append("poor_rank")

            answer_eval = answer_lookup.get(query)
            if answer_eval and answer_eval.get("faithfulness", 1.0) < 0.5:
                failure_modes.append("unfaithful_answer")

            verdict = verdict_lookup.get(query)
            if verdict and verdict.get("verdict") == "fail":
                failure_modes.append("judge_rejected")

            if failure_modes:
                failures.append({"query": query, "failure_modes": failure_modes})

        summary = Counter(mode for item in failures for mode in item["failure_modes"])
        return {"failures": failures, "summary": dict(summary)}


@registry.register(
    NodeMetadata(
        name="ABTestingNode",
        description=(
            "Compare variants using metrics and feedback signals to select a winner."
        ),
        category="conversational_search",
    )
)
class ABTestingNode(TaskNode):
    """Select the best variant using evaluation metrics and feedback signals."""

    variant_metrics_key: str = Field(default="variants")
    feedback_key: str = Field(default="feedback")
    primary_metric: str = Field(default="score")
    minimum_metric: float = Field(default=0.0, ge=0.0)
    feedback_penalty: float = Field(default=0.05, ge=0.0, le=1.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Select a winning variant using metrics and feedback."""
        variant_metrics = _resolve_payload(
            state, self.variant_metrics_key, self.variant_metrics_key
        )
        feedback = _resolve_payload(state, self.feedback_key, self.feedback_key) or []

        if not isinstance(variant_metrics, dict):
            msg = "ABTestingNode requires a mapping of variant metrics"
            raise ValueError(msg)
        if not isinstance(feedback, list):
            msg = "Feedback payload must be a list"
            raise ValueError(msg)

        feedback_summary = self._summarize_feedback(feedback)
        scored_variants: dict[str, float] = {}
        for name, metrics in variant_metrics.items():
            if not isinstance(metrics, dict):
                continue
            metric_value = float(metrics.get(self.primary_metric, 0.0))
            adjusted = max(
                0.0,
                metric_value - feedback_summary.get(name, 0.0) * self.feedback_penalty,
            )
            if metric_value < self.minimum_metric:
                adjusted = 0.0
            scored_variants[name] = adjusted

        if not scored_variants:
            msg = "No variants to compare in ABTestingNode"
            raise ValueError(msg)

        winner = max(scored_variants, key=lambda variant: scored_variants[variant])
        reason = f"Selected {winner} using {self.primary_metric} adjusted for feedback"
        return {"winner": winner, "variant_scores": scored_variants, "reason": reason}

    def _summarize_feedback(self, feedback: list[dict[str, Any]]) -> dict[str, float]:
        summary: dict[str, float] = {}
        for entry in feedback:
            variant = entry.get("variant") or ""
            sentiment = entry.get("sentiment", "neutral")
            if not variant:
                continue
            delta = 1.0 if sentiment == "negative" else 0.0
            summary[variant] = summary.get(variant, 0.0) + delta
        return summary


@registry.register(
    NodeMetadata(
        name="UserFeedbackCollectionNode",
        description="Collect user feedback for later ingestion.",
        category="conversational_search",
    )
)
class UserFeedbackCollectionNode(TaskNode):
    """Validate and normalize user feedback records."""

    feedback_input_key: str = Field(default="feedback")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Normalize free-form feedback into a consistent schema."""
        inputs = state.get("inputs", {})
        feedback = inputs.get(self.feedback_input_key)
        if not isinstance(feedback, list):
            msg = "UserFeedbackCollectionNode expects a list of feedback items"
            raise ValueError(msg)

        normalized: list[dict[str, Any]] = []
        for entry in feedback:
            if not isinstance(entry, dict):
                continue
            normalized.append(
                {
                    "user_id": entry.get("user_id", "anonymous"),
                    "variant": entry.get("variant"),
                    "rating": entry.get("rating", 0),
                    "comment": (entry.get("comment") or "").strip(),
                    "sentiment": entry.get("sentiment", "neutral"),
                }
            )

        averages = (
            mean([item.get("rating", 0) for item in normalized]) if normalized else 0.0
        )
        return {"feedback": normalized, "average_rating": averages}


@registry.register(
    NodeMetadata(
        name="FeedbackIngestionNode",
        description="Transform collected feedback into audit-friendly records.",
        category="conversational_search",
    )
)
class FeedbackIngestionNode(TaskNode):
    """Persistable representation of user feedback."""

    feedback_result_key: str = Field(default="feedback")
    timestamp_field: str = Field(default="ingested_at")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Attach ingestion timestamps to feedback entries."""
        feedback = _resolve_payload(
            state, self.feedback_result_key, self.feedback_result_key
        )
        if not isinstance(feedback, list):
            msg = "FeedbackIngestionNode expects feedback list"
            raise ValueError(msg)

        ingested = []
        now = datetime.utcnow().isoformat()
        for entry in feedback:
            if not isinstance(entry, dict):
                continue
            entry[self.timestamp_field] = now
            ingested.append(entry)

        return {"ingested_feedback": ingested, "count": len(ingested)}


@registry.register(
    NodeMetadata(
        name="AnalyticsExportNode",
        description=(
            "Aggregate evaluation metrics and feedback for downstream analytics."
        ),
        category="conversational_search",
    )
)
class AnalyticsExportNode(TaskNode):
    """Create analytics export bundle combining metrics and feedback."""

    retrieval_key: str = Field(default="retrieval_evaluation")
    answer_key: str = Field(default="answer_quality")
    judge_key: str = Field(default="llm_judge")
    failures_key: str = Field(default="failure_analysis")
    feedback_key: str = Field(default="feedback")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Bundle evaluation outputs for downstream analytics sinks."""
        bundle = {
            "retrieval_metrics": _resolve_payload(state, self.retrieval_key, "metrics")
            or {},
            "answer_metrics": _resolve_payload(state, self.answer_key, "metrics") or {},
            "judge": _resolve_payload(state, self.judge_key, "verdicts") or [],
            "failures": _resolve_payload(state, self.failures_key, "failures") or [],
            "feedback": _resolve_payload(state, self.feedback_key, self.feedback_key)
            or [],
        }
        bundle["exported_at"] = datetime.utcnow().isoformat()
        return bundle


@registry.register(
    NodeMetadata(
        name="PolicyComplianceNode",
        description="Validate outputs against policy rules and emit audit logs.",
        category="conversational_search",
    )
)
class PolicyComplianceNode(TaskNode):
    """Check generated content against allow/block lists."""

    content_key: str = Field(default="answer")
    blocked_terms: list[str] = Field(
        default_factory=list, description="Terms that violate compliance policies"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Check text for blocked terms and emit an audit trail."""
        inputs = state.get("inputs", {})
        content = inputs.get(self.content_key, "")
        if not isinstance(content, str):
            msg = "PolicyComplianceNode expects content as a string"
            raise ValueError(msg)

        violations = [
            term for term in self.blocked_terms if term.lower() in content.lower()
        ]
        compliant = not violations
        audit_log = {
            "checked_at": datetime.utcnow().isoformat(),
            "violations": violations,
            "content_preview": content[:200],
        }
        return {"compliant": compliant, "audit_log": audit_log}


@registry.register(
    NodeMetadata(
        name="MemoryPrivacyNode",
        description="Redact sensitive information from memory records with logging.",
        category="conversational_search",
    )
)
class MemoryPrivacyNode(TaskNode):
    """Remove potential PII from memory entries."""

    memories_key: str = Field(default="memories")
    redaction_token: str = Field(default="[REDACTED]")

    email_pattern: ClassVar[Pattern[str]] = re.compile(r"[\w.\-]+@[\w.\-]+")
    phone_pattern: ClassVar[Pattern[str]] = re.compile(r"\+?\d[\d\s\-]{7,}\d")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Redact basic PII patterns from memory entries."""
        inputs = state.get("inputs", {})
        memories = inputs.get(self.memories_key)
        if not isinstance(memories, list):
            msg = "MemoryPrivacyNode expects a list of memories"
            raise ValueError(msg)

        redacted = []
        for entry in memories:
            if not isinstance(entry, dict):
                continue
            content = str(entry.get("content", ""))
            scrubbed = self._redact(content)
            audit = {
                "original_length": len(content),
                "redacted_length": len(scrubbed),
                "had_pii": scrubbed != content,
            }
            redacted.append({**entry, "content": scrubbed, "audit": audit})

        return {"memories": redacted}

    def _redact(self, text: str) -> str:
        text = self.email_pattern.sub(self.redaction_token, text)
        text = self.phone_pattern.sub(self.redaction_token, text)
        return text


@registry.register(
    NodeMetadata(
        name="DataAugmentationNode",
        description=(
            "Generate simple synthetic variants of dataset queries and answers."
        ),
        category="conversational_search",
    )
)
class DataAugmentationNode(TaskNode):
    """Create augmented dataset entries for training and evaluation."""

    dataset_result_key: str = Field(default="dataset")
    dataset_field: str = Field(default="dataset")
    augmentation_suffix: str = Field(default="(augmented)")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Expand datasets with simple paraphrased entries."""
        dataset_payload = _resolve_payload(
            state, self.dataset_result_key, self.dataset_field
        )
        if not isinstance(dataset_payload, list):
            msg = "DataAugmentationNode requires dataset records"
            raise ValueError(msg)

        dataset = [DatasetRecord.model_validate(item) for item in dataset_payload]
        augmented: list[DatasetRecord] = []

        for record in dataset:
            augmented.append(record)
            augmented.append(
                DatasetRecord(
                    query=f"{record.query} {self.augmentation_suffix}",
                    relevant_ids=record.relevant_ids,
                    reference_answer=record.reference_answer,
                    context=record.context,
                )
            )

        return {"dataset": augmented, "augmentations": len(augmented) - len(dataset)}


@registry.register(
    NodeMetadata(
        name="TurnAnnotationNode",
        description="Annotate conversation turns with speaker roles and labels.",
        category="conversational_search",
    )
)
class TurnAnnotationNode(TaskNode):
    """Add annotations to conversational turns for downstream analysis."""

    turns_input_key: str = Field(default="turns")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Annotate conversation turns with roles, intent, and token counts."""
        inputs = state.get("inputs", {})
        turns = inputs.get(self.turns_input_key)
        if not isinstance(turns, list):
            msg = "TurnAnnotationNode expects a list of turns"
            raise ValueError(msg)

        annotated = []
        for index, turn in enumerate(turns):
            if not isinstance(turn, dict):
                continue
            text = str(turn.get("text", ""))
            role = turn.get("role", "user" if index % 2 == 0 else "assistant")
            intent = "question" if text.endswith("?") else "statement"
            annotated.append(
                {
                    **turn,
                    "role": role,
                    "intent": intent,
                    "token_count": len(text.split()),
                }
            )

        return {"turns": annotated}
