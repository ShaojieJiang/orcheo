"""Evaluation, analytics, compliance, and augmentation nodes."""

from __future__ import annotations
import json
import logging
import math
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.conversation import MemoryTurn
from orcheo.nodes.registry import NodeMetadata, registry


def _tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"\W+", text.lower()) if token]


logger = logging.getLogger(__name__)


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
    limit_key: str = Field(default="limit")
    references_key: str = Field(default="references")
    keyword_corpus_key: str = Field(default="keyword_corpus")
    dataset: list[dict[str, Any]] = Field(default_factory=list)
    references: dict[str, str] = Field(default_factory=dict)
    keyword_corpus: list[dict[str, str]] = Field(default_factory=list)
    golden_path: str | None = Field(
        default=None, description="Path to golden dataset JSON."
    )
    queries_path: str | None = Field(
        default=None, description="Path to baseline queries JSON."
    )
    labels_path: str | None = Field(
        default=None, description="Path to relevance labels JSON."
    )
    docs_path: str | None = Field(
        default=None, description="Path to knowledge base docs."
    )
    http_timeout: float = Field(
        default=30.0, ge=0.0, description="Timeout in seconds for URL-based datasets."
    )
    split: str | None = Field(
        default=None, description="Optional dataset split when loading from files."
    )
    limit: int | None = Field(
        default=None, ge=1, description="Optional dataset cap when loading from files."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a dataset filtered by split and limited when requested."""
        del config
        inputs = state.get("inputs") or {}
        state["inputs"] = inputs

        requested_split = inputs.get(self.split_key, self.split)
        requested_limit = inputs.get(self.limit_key, self.limit)

        dataset = self._dataset_from_inputs(inputs)
        references = self._references_from_inputs(inputs)
        keyword_corpus = self._keyword_corpus_from_inputs(inputs)

        dataset, references, keyword_corpus = await self._load_if_needed(
            dataset, references, keyword_corpus, requested_split, requested_limit
        )
        dataset, references, keyword_corpus = self._validate_inputs(
            dataset, references, keyword_corpus
        )

        dataset = self._filter_dataset(dataset, requested_split, requested_limit)

        self._update_inputs(
            inputs,
            dataset,
            references,
            keyword_corpus,
            requested_split,
            requested_limit,
        )

        return {
            "dataset": dataset,
            "references": references,
            "keyword_corpus": keyword_corpus,
            "count": len(dataset),
            "split": requested_split,
            "limit": requested_limit,
        }

    def _dataset_from_inputs(self, inputs: dict[str, Any]) -> Any:
        dataset = inputs.get(self.dataset_key)
        if dataset is not None:
            return dataset
        return self.dataset

    def _references_from_inputs(self, inputs: dict[str, Any]) -> dict[str, str] | None:
        references = inputs.get(self.references_key)
        if references is not None:
            return references
        return self.references or None

    def _keyword_corpus_from_inputs(
        self, inputs: dict[str, Any]
    ) -> list[dict[str, str]] | None:
        keyword_corpus = inputs.get(self.keyword_corpus_key)
        if keyword_corpus is not None:
            return keyword_corpus
        return self.keyword_corpus or None

    async def _load_if_needed(
        self,
        dataset: Any,
        references: dict[str, str] | None,
        keyword_corpus: list[dict[str, str]] | None,
        split: str | None,
        limit: int | None,
    ) -> tuple[
        list[dict[str, Any]], dict[str, str] | None, list[dict[str, str]] | None
    ]:
        if not self._should_load_from_files(dataset):
            return dataset, references, keyword_corpus

        dataset, loaded_references, loaded_corpus = await self._load_from_files(
            split, limit
        )
        references = references if references is not None else loaded_references
        keyword_corpus = keyword_corpus if keyword_corpus is not None else loaded_corpus
        return dataset, references, keyword_corpus

    def _validate_inputs(
        self,
        dataset: Any,
        references: dict[str, str] | None,
        keyword_corpus: list[dict[str, str]] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, str]]]:
        if not isinstance(dataset, list):
            msg = "DatasetNode expects dataset to be a list"
            raise ValueError(msg)
        if references is None:
            references = {}
        if keyword_corpus is None:
            keyword_corpus = []
        if not isinstance(references, dict):
            msg = "DatasetNode expects references to be a dict"
            raise ValueError(msg)
        if not isinstance(keyword_corpus, list):
            msg = "DatasetNode expects keyword_corpus to be a list"
            raise ValueError(msg)
        return dataset, references, keyword_corpus

    def _update_inputs(
        self,
        inputs: dict[str, Any],
        dataset: list[dict[str, Any]],
        references: dict[str, str] | None,
        keyword_corpus: list[dict[str, str]] | None,
        split: str | None,
        limit: int | None,
    ) -> None:
        inputs[self.dataset_key] = dataset
        inputs[self.references_key] = references or {}
        inputs[self.keyword_corpus_key] = keyword_corpus or []
        if split is not None:
            inputs[self.split_key] = split
        if limit is not None:  # pragma: no branch
            inputs[self.limit_key] = limit

    def _filter_dataset(
        self,
        dataset: list[dict[str, Any]],
        split: str | None,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        filtered = dataset
        if isinstance(split, str):
            filtered = [row for row in filtered if row.get("split") == split]

        if isinstance(limit, int) and limit > 0:
            filtered = filtered[:limit]
        return filtered

    def _should_load_from_files(self, dataset: Any) -> bool:
        if not self._has_file_sources():
            return False
        if dataset is None:
            return True
        return isinstance(dataset, list) and not dataset

    def _has_file_sources(self) -> bool:
        return any(
            [
                self.golden_path,
                self.queries_path,
                self.labels_path,
                self.docs_path,
            ]
        )

    async def _load_from_files(
        self,
        split: str | None,
        limit: int | None,
    ) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, str]]]:
        missing = [
            name
            for name, value in {
                "golden_path": self.golden_path,
                "queries_path": self.queries_path,
                "labels_path": self.labels_path,
                "docs_path": self.docs_path,
            }.items()
            if not value
        ]
        if missing:
            msg = f"DatasetNode requires {', '.join(missing)} to load from files"
            raise ValueError(msg)

        golden_data = await self._load_json(self.golden_path)
        queries_data = await self._load_json(self.queries_path)
        labels_data = await self._load_json(self.labels_path)

        label_map: dict[str, list[str]] = {}
        for entry in labels_data:
            query_id = str(entry.get("query_id"))
            label_map.setdefault(query_id, [])
            doc_id = str(entry.get("doc_id"))
            label_map[query_id].append(doc_id)

        dataset: list[dict[str, Any]] = []
        references: dict[str, str] = {}
        active_split = split or self.split

        for item in golden_data:
            query_id = str(item.get("id"))
            relevant_ids = [
                str(doc) for doc in item.get("expected_citations", []) if doc
            ]
            dataset.append(
                {
                    "id": query_id,
                    "query": item.get("query", ""),
                    "relevant_ids": relevant_ids,
                    "split": active_split or item.get("split", "test"),
                }
            )
            references[query_id] = item.get("expected_answer", "")

        for item in queries_data:
            query_id = str(item.get("id"))
            dataset.append(
                {
                    "id": query_id,
                    "query": item.get("question", ""),
                    "relevant_ids": label_map.get(query_id, []),
                    "split": active_split or item.get("split", "test"),
                }
            )

        dataset = self._filter_dataset(dataset, active_split, limit)
        keyword_corpus = self.keyword_corpus or self._build_keyword_corpus()

        return dataset, references, keyword_corpus

    async def _load_json(self, path: str | None) -> Any:
        if path is None:
            msg = "JSON path must be provided."
            raise ValueError(msg)
        if self._is_url(path):
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.get(path)
                response.raise_for_status()
                return response.json()
        with Path(path).open("r", encoding="utf-8") as file:
            return json.load(file)

    def _is_url(self, path: str) -> bool:
        return path.startswith(("http://", "https://"))

    def _build_keyword_corpus(self) -> list[dict[str, str]]:
        if self.docs_path is None:
            return []
        corpus: list[dict[str, str]] = []
        for path in sorted(Path(self.docs_path).glob("*.md")):
            content = path.read_text(encoding="utf-8")
            corpus.append(
                {"id": path.name, "content": content.strip(), "source": path.name}
            )
        return corpus


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
    k: int | str = Field(default=5)

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
        k = int(self.k)
        for example in dataset:
            query_id = example.get("id")
            relevant_ids: set[str] = set(example.get("relevant_ids", []))
            returned = result_map.get(query_id, [])[:k]
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
    blocked_terms: list[str] | str = Field(default_factory=lambda: ["password", "ssn"])

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Apply policy checks and return sanitized content with audit metadata."""
        content = state.get("inputs", {}).get(self.text_key, "")
        if not isinstance(content, str):
            msg = "PolicyComplianceNode expects content string"
            raise ValueError(msg)

        if isinstance(self.blocked_terms, list):
            blocked_terms = self.blocked_terms
        elif isinstance(self.blocked_terms, str):
            try:
                parsed = json.loads(self.blocked_terms)
                blocked_terms = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                blocked_terms = [self.blocked_terms]
        else:
            blocked_terms = []

        violations = self._detect_violations(content, blocked_terms)
        sanitized = self._sanitize(content, blocked_terms)
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

    def _detect_violations(self, content: str, blocked_terms: list[str]) -> list[str]:
        violations: list[str] = []
        for term in blocked_terms:
            if re.search(rf"\b{re.escape(term)}\b", content, re.IGNORECASE):
                violations.append(f"blocked_term:{term}")
        if re.search(r"\b\d{3}-\d{2}-\d{4}\b", content):
            violations.append("pii:ssn_pattern")
        if re.search(r"\b\S+@\S+\.[a-z]{2,}\b", content, re.IGNORECASE):
            violations.append("pii:email")
        return violations

    def _sanitize(self, content: str, blocked_terms: list[str]) -> str:
        sanitized = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]", content)
        sanitized = re.sub(r"\b\S+@\S+\.[a-z]{2,}\b", "[REDACTED_EMAIL]", sanitized)
        for term in blocked_terms:
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
    retention_count: int | str | None = Field(default=None)

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

        retention_count_int = (
            int(self.retention_count) if self.retention_count is not None else None
        )
        if retention_count_int is not None:
            sanitized_history = sanitized_history[-retention_count_int:]

        return {
            "sanitized_history": sanitized_history,
            "redaction_count": redactions,
            "truncated": retention_count_int is not None
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
