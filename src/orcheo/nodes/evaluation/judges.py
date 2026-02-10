"""LLM judge, failure analysis, and A/B testing nodes."""

from __future__ import annotations
import json
import logging
import re
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.evaluation.metrics import _tokenize
from orcheo.nodes.registry import NodeMetadata, registry


logger = logging.getLogger(__name__)


@registry.register(
    NodeMetadata(
        name="LLMJudgeNode",
        description="Apply lightweight, AI model judging heuristics.",
        category="conversational_search",
    )
)
class LLMJudgeNode(TaskNode):
    """Simulate LLM-as-a-judge with transparent heuristics."""

    answers_key: str = Field(default="answers")
    min_score: float | str = Field(default=0.5)
    ai_model: str | None = Field(
        default=None, description="Optional model identifier for the judge."
    )
    model_kwargs: dict[str, Any] | str = Field(
        default_factory=dict,
        description="Additional keyword arguments passed to init_chat_model.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Apply lightweight judging heuristics to answers."""
        min_score = float(self.min_score)
        answers = state.get("inputs", {}).get(self.answers_key)
        if not isinstance(answers, list):
            msg = "LLMJudgeNode expects answers list"
            raise ValueError(msg)

        if self.ai_model:
            try:
                return await self._judge_with_model(answers, min_score)
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning(
                    "LLMJudgeNode falling back to heuristic scoring: %s", exc
                )

        return self._judge_with_heuristics(answers, min_score)

    async def _judge_with_model(
        self, answers: list[dict[str, Any]], min_score: float
    ) -> dict[str, Any]:
        """Use configured AI model to score answers."""
        from langchain.chat_models import init_chat_model
        from langchain_core.messages import HumanMessage, SystemMessage

        kwargs = self.model_kwargs if isinstance(self.model_kwargs, dict) else {}
        model = init_chat_model(self.ai_model, **kwargs)
        verdicts: list[dict[str, Any]] = []
        passing = 0

        system_message = SystemMessage(
            content=(
                "You are an evaluation judge. Score the assistant's answer between "
                "0 and 1 for factual accuracy, safety, and completeness. "
                "Respond ONLY with JSON: "
                '{"score": <float 0-1>, "flags": ["flag1", ...]}. '
                "Use the 'flags' array to note issues like 'safety' or "
                "'low_confidence'."
            )
        )

        for entry in answers:
            content = str(entry.get("answer", ""))
            messages = [
                system_message,
                HumanMessage(content=f"Assistant answer:\n{content}"),
            ]
            response = await model.ainvoke(messages)
            score, flags = self._parse_model_response(response, content)
            approved = score >= min_score
            verdict = {
                "id": entry.get("id"),
                "score": score,
                "approved": approved,
                "flags": flags,
            }
            passing += int(approved)
            verdicts.append(verdict)

        return {
            "approved_ratio": passing / len(verdicts) if verdicts else 0.0,
            "verdicts": verdicts,
        }

    def _parse_model_response(
        self, response: Any, fallback_content: str
    ) -> tuple[float, list[str]]:
        """Parse score/flags from model output, with heuristic fallback."""
        text = ""
        if hasattr(response, "content"):
            raw_content = response.content  # type: ignore[attr-defined]
            text = raw_content if isinstance(raw_content, str) else str(raw_content)
        elif isinstance(response, dict):
            text = str(response.get("content", ""))
        else:
            text = str(response)

        score: float | None = None
        flags: list[str] = []

        try:
            payload = json.loads(text)
            if isinstance(payload, dict):  # pragma: no branch
                raw_score = payload.get("score")
                if isinstance(raw_score, int | float):
                    score = float(raw_score)
                raw_flags = payload.get("flags")
                if isinstance(raw_flags, list):
                    flags = [str(item) for item in raw_flags]
        except json.JSONDecodeError:
            pass

        if score is None:
            match = re.search(r"\b(0?\.\d+|1(?:\.0+)?)\b", text)
            if match:
                score = float(match.group(1))

        if score is None:
            score = self._score(fallback_content)
            flags = self._flags(fallback_content)

        return max(min(score, 1.0), 0.0), flags

    def _judge_with_heuristics(
        self, answers: list[dict[str, Any]], min_score: float
    ) -> dict[str, Any]:
        """Fallback heuristic judging used when no model is configured."""
        verdicts: list[dict[str, Any]] = []
        passing = 0
        for entry in answers:
            answer_id = entry.get("id")
            content = str(entry.get("answer", ""))
            score = self._score(content)
            approved = score >= min_score
            verdict = {
                "id": answer_id,
                "score": score,
                "approved": approved,
                "flags": self._flags(content),
            }
            passing += int(approved)
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
    recall_threshold: float | str = Field(default=0.6)
    faithfulness_threshold: float | str = Field(default=0.6)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Flag failure categories using metrics and feedback signals."""
        recall_threshold = float(self.recall_threshold)
        faithfulness_threshold = float(self.faithfulness_threshold)
        inputs = state.get("inputs", {})
        retrieval_metrics = inputs.get(self.retrieval_metrics_key, {})
        answer_metrics = inputs.get(self.answer_metrics_key, {})
        feedback = inputs.get(self.feedback_key, []) or []

        categories: set[str] = set()
        if retrieval_metrics.get("recall_at_k", 1.0) < recall_threshold:
            categories.add("low_recall")
        if answer_metrics.get("faithfulness", 1.0) < faithfulness_threshold:
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
    min_metric_threshold: float | str = Field(default=0.5)
    min_feedback_score: float | str = Field(default=0.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Rank A/B variants and apply rollout gating criteria."""
        min_metric_threshold = float(self.min_metric_threshold)
        min_feedback_score = float(self.min_feedback_score)
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
            winner.get(self.primary_metric, 0.0) >= min_metric_threshold
        )
        if evaluation_metrics:
            metrics_to_evaluate = [
                normalized
                for value in evaluation_metrics.values()
                if (normalized := self._normalize_evaluation_metric(value)) is not None
            ]
            if metrics_to_evaluate:  # pragma: no branch
                rollout_allowed = rollout_allowed and all(
                    metric >= min_metric_threshold for metric in metrics_to_evaluate
                )

        feedback_score = inputs.get("feedback_score")
        if isinstance(feedback_score, int | float):
            rollout_allowed = rollout_allowed and feedback_score >= min_feedback_score

        return {
            "winner": winner,
            "ranking": ranked,
            "rollout_allowed": rollout_allowed,
        }

    def _normalize_evaluation_metric(self, value: Any) -> float | None:
        """Extract a comparable numeric value from evaluation metric payloads."""
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, dict):
            metric_candidates: list[float] = []
            primary_candidate = value.get(self.primary_metric)
            if isinstance(primary_candidate, int | float):
                return float(primary_candidate)
            score_candidate = value.get("score")
            if isinstance(score_candidate, int | float):
                return float(score_candidate)
            metric_candidates.extend(
                float(val) for val in value.values() if isinstance(val, int | float)
            )
            if metric_candidates:
                return max(metric_candidates)
        return None  # pragma: no cover - defensive fallback
