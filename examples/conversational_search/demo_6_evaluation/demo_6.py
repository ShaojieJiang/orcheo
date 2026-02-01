"""Evaluation & Research demo showcasing metrics, A/B testing, and feedback loops."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.embedding_registry import (
    OPENAI_TEXT_EMBEDDING_3_SMALL,
    PINECONE_BM25_DEFAULT,
)
from orcheo.nodes.conversational_search.evaluation import (
    ABTestingNode,
    AnalyticsExportNode,
    AnswerQualityEvaluationNode,
    DataAugmentationNode,
    DatasetNode,
    FailureAnalysisNode,
    FeedbackIngestionNode,
    LLMJudgeNode,
    RetrievalEvaluationNode,
    TurnAnnotationNode,
    UserFeedbackCollectionNode,
)
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.conversational_search.retrieval import (
    DenseSearchNode,
    HybridFusionNode,
    SparseSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    PineconeVectorStore,
)


SESSION_ID = "demo-6-evaluation-session"
DATA_DIR = (
    "https://raw.githubusercontent.com/ShaojieJiang/orcheo/"
    "refs/heads/main/examples/conversational_search/data"
)
RECURSION_LIMIT = 250


DEFAULT_CONFIG: dict[str, Any] = {
    "dataset": {
        "golden_path": DATA_DIR + "/golden/golden_dataset.json",
        "queries_path": DATA_DIR + "/queries.json",
        "labels_path": DATA_DIR + "/labels/relevance_labels.json",
        "docs_path": "https://raw.githubusercontent.com/ShaojieJiang/orcheo/refs/heads/main/examples/conversational_search/data/docs/product_overview.md",
        "split": "test",
        "limit": None,
    },
    "retrieval": {
        "top_k": 4,
        "embedding_method": OPENAI_TEXT_EMBEDDING_3_SMALL,
        "sparse_embedding_method": PINECONE_BM25_DEFAULT,
        "sparse_top_k": 4,
        "sparse_candidate_k": 50,
        "sparse_score_threshold": 0.0,
        "fusion": {
            "strategy": "rrf",
            "rrf_k": 30,
            "top_k": 4,
        },
    },
    "vector_store": {
        "type": "pinecone",
        "pinecone": {
            "index_name": "orcheo-demo-dense",
            "namespace": "hybrid_search",
            "client_kwargs": {"api_key": "[[pinecone_api_key]]"},
        },
    },
    "sparse_vector_store": {
        "type": "pinecone",
        "pinecone": {
            "index_name": "orcheo-demo-sparse",
            "namespace": "hybrid_search",
            "client_kwargs": {"api_key": "[[pinecone_api_key]]"},
        },
    },
    "generation": {
        "citation_style": "inline",
        "model": "openai:gpt-4o-mini",
    },
    "ab_testing": {
        "experiment_id": "retrieval_comparison_001",
        "min_metric_threshold": 0.35,
    },
    "llm_judge": {"min_score": 0.5, "model": "openai:gpt-4o-mini"},
}


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base`` without mutation."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_vector_store_from_config(
    cfg: dict[str, Any],
    *,
    store_kind: str = "vector",
) -> BaseVectorStore:
    """Instantiate the Pinecone vector store populated by Demo 0."""
    store_type = str(cfg.get("type", "pinecone")).lower()
    if store_type != "pinecone":
        msg = f"Demo 6 expects a Pinecone {store_kind} vector store seeded by Demo 1."
        raise ValueError(msg)

    pinecone_cfg = dict(cfg.get("pinecone") or cfg)
    index_name = pinecone_cfg.get("index_name")
    if not index_name:
        msg = f"Pinecone {store_kind} configuration requires 'index_name'"
        raise ValueError(msg)

    client_kwargs = dict(pinecone_cfg.get("client_kwargs") or {})
    return PineconeVectorStore(
        index_name=index_name,
        namespace=pinecone_cfg.get("namespace"),
        client_kwargs=client_kwargs,
    )


class ResultToInputsNode(TaskNode):
    """Copy values from a result payload into graph inputs."""

    source_result_key: str = Field(description="Result entry to read from.")
    mappings: dict[str, str] = Field(
        description="Mapping of target input key -> source field path",
    )
    allow_missing: bool = Field(
        default=True,
        description="If false, missing source fields raise an error.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Populate inputs using configured mappings."""
        del config
        payload = state.get("results", {}).get(self.source_result_key, {})
        if not isinstance(payload, dict):
            return {"mapped_keys": []}

        inputs = state.get("inputs") or {}
        state["inputs"] = inputs

        mapped: list[str] = []
        for target_key, source_path in self.mappings.items():
            value = payload
            for segment in source_path.split("."):
                if not isinstance(value, dict) or segment not in value:
                    value = None
                    break
                value = value.get(segment)
            if value is None:
                if not self.allow_missing:
                    msg = f"Field '{source_path}' missing from {self.source_result_key}"
                    raise ValueError(msg)
                continue
            inputs[target_key] = value
            mapped.append(target_key)
        return {"mapped_keys": mapped}


class VariantRetrievalNode(TaskNode):
    """Run dense-only and hybrid retrieval variants for evaluation."""

    dense_retriever: DenseSearchNode = Field(description="Primary dense retriever.")
    sparse_retriever: SparseSearchNode = Field(
        description="Sparse retriever backed by Pinecone."
    )
    fusion_node: HybridFusionNode = Field(description="Fusion node for hybrid path.")
    query_field: str = Field(
        default="query",
        description="Field name inside dataset entries containing the query text.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute both variants across the dataset."""
        inputs = state.get("inputs", {}) or {}
        dataset = inputs.get("dataset") or []
        if not isinstance(dataset, list):
            msg = "VariantRetrievalNode requires a dataset list in inputs"
            raise ValueError(msg)

        vector_only: list[dict[str, Any]] = []
        hybrid: list[dict[str, Any]] = []
        samples: list[dict[str, Any]] = []

        for entry in dataset:
            query = entry.get(self.query_field, "")
            query_id = str(entry.get("id"))
            dense_state = State({"inputs": {"query": query}, "results": {}})
            dense_payload = await self.dense_retriever.run(dense_state, config)
            dense_results = self.normalize_results(dense_payload.get("results", []))
            vector_only.append({"query_id": query_id, "results": dense_results})

            sparse_state = State({"inputs": {"query": query}, "results": {}})
            sparse_payload = await self.sparse_retriever.run(sparse_state, config)
            sparse_results = self.normalize_results(sparse_payload.get("results", []))
            fusion_state = State(
                {
                    "inputs": {},
                    "results": {
                        self.fusion_node.results_field: {
                            "dense": dense_results,
                            "sparse": sparse_results,
                        }
                    },
                }
            )
            fusion_payload = await self.fusion_node.run(fusion_state, config)
            fused_results = self.normalize_results(fusion_payload.get("results", []))
            hybrid.append({"query_id": query_id, "results": fused_results})

            if dense_results:
                samples.append(
                    {
                        "query": query,
                        "variant": "vector_only",
                        "top_hit": dense_results[0].get("id"),
                    }
                )
            if fused_results:
                samples.append(
                    {
                        "query": query,
                        "variant": "hybrid_fusion",
                        "top_hit": fused_results[0].get("id"),
                    }
                )

        return {
            "vector_only_results": vector_only,
            "hybrid_results": hybrid,
            "samples": samples[:4],
        }

    def normalize_results(self, entries: list[Any]) -> list[dict[str, Any]]:
        """Convert heterogeneous retrieval outputs into normalized dicts."""
        normalized: list[dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, SearchResult):
                normalized.append(entry.model_dump())
                continue
            if isinstance(entry, dict):
                normalized.append(
                    {
                        "id": str(entry.get("id")),
                        "score": float(entry.get("score", 0.0)),
                        "text": entry.get("text", ""),
                        "metadata": entry.get("metadata", {}) or {},
                        "source": entry.get("source"),
                        "sources": entry.get("sources", []),
                    }
                )
        return normalized


class BatchGenerationNode(TaskNode):
    """Generate answers for each query using a shared generator node."""

    generator: GroundedGeneratorNode = Field(description="Generator node.")
    retrieval_key: str = Field(
        default="hybrid_results",
        description="Input key containing fused retrieval results.",
    )
    query_field: str = Field(default="query", description="Query field name.")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate answers and conversation history across the dataset."""
        dataset = state.get("inputs", {}).get("dataset") or []
        retrieval_results = state.get("inputs", {}).get(self.retrieval_key) or []
        if not isinstance(dataset, list) or not isinstance(retrieval_results, list):
            msg = "BatchGenerationNode requires dataset and retrieval results"
            raise ValueError(msg)

        retrieval_map = {
            str(entry.get("query_id")): entry.get("results", [])
            for entry in retrieval_results
        }

        answers: list[dict[str, Any]] = []
        conversation_history: list[dict[str, Any]] = []

        for example in dataset:
            query = example.get(self.query_field, "")
            query_id = str(example.get("id"))
            context_entries = retrieval_map.get(query_id, [])
            context_results = [
                SearchResult.model_validate(item) for item in context_entries
            ]
            generator_state = State(
                {
                    "inputs": {"query": query},
                    "results": {"generation_context": {"results": context_results}},
                }
            )
            payload = await self.generator.run(generator_state, config)
            answers.append(
                {
                    "id": query_id,
                    "answer": payload.get("reply", ""),
                    "citations": payload.get("citations", []),
                }
            )
            conversation_history.extend(
                [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": payload.get("reply", "")},
                ]
            )

        return {"answers": answers, "conversation_history": conversation_history}


class FeedbackSynthesisNode(TaskNode):
    """Derive a lightweight feedback signal from evaluation metrics."""

    retrieval_metric_key: str = Field(
        default="recall_at_k",
        description="Primary retrieval metric to drive rating.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compute a numeric rating and short comment."""
        del config
        results = state.get("results", {})
        retrieval_metrics = results.get("retrieval_eval_hybrid", {}).get("metrics", {})
        answer_metrics = results.get("answer_quality", {}).get("metrics", {})
        recall = retrieval_metrics.get(self.retrieval_metric_key, 0.0)
        faithfulness = answer_metrics.get("faithfulness", 0.0)
        blended = (recall + faithfulness) / 2
        rating = max(1, min(5, int(round(1 + blended * 4))))
        comment = (
            "Hybrid variant shows stronger recall."
            if recall >= 0.5
            else "Improve retrieval relevance before rollout."
        )
        return {"rating": rating, "comment": comment}


class FeedbackNormalizerNode(TaskNode):
    """Normalize feedback into a list for downstream processing."""

    feedback_key: str = Field(
        default="feedback",
        description="Input key containing feedback entries.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Ensure feedback is represented as a list of entries."""
        del config
        inputs = state.get("inputs") or {}
        state["inputs"] = inputs
        feedback = inputs.get(self.feedback_key)
        if feedback is None:
            normalized: list[Any] = []
        elif isinstance(feedback, list):
            normalized = feedback
        else:
            normalized = [feedback]
        inputs[self.feedback_key] = normalized
        return {"count": len(normalized)}


class VariantScoringNode(TaskNode):
    """Build variant payloads for A/B testing."""

    primary_metric: str = Field(
        default="score",
        description="Field used by ABTestingNode as the ranking metric.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Assemble variants and evaluation metrics for AB testing."""
        del config
        results = state.get("results", {})
        vector_metrics = results.get("retrieval_eval_vector", {}).get("metrics", {})
        hybrid_metrics = results.get("retrieval_eval_hybrid", {}).get("metrics", {})
        answer_metrics = results.get("answer_quality", {}).get("metrics", {})

        variants = [
            {
                "name": "vector_only",
                self.primary_metric: self.score_variant(vector_metrics, answer_metrics),
                "details": vector_metrics,
            },
            {
                "name": "hybrid_fusion",
                self.primary_metric: self.score_variant(hybrid_metrics, answer_metrics),
                "details": hybrid_metrics,
            },
        ]

        return {
            "variants": variants,
            "evaluation_metrics": {
                "vector_only": vector_metrics,
                "hybrid_fusion": hybrid_metrics,
                "answer_quality": answer_metrics,
            },
        }

    def score_variant(
        self, retrieval_metrics: dict[str, Any], answer_metrics: dict[str, Any]
    ) -> float:
        """Blend retrieval and answer quality metrics into a sortable score."""
        recall = retrieval_metrics.get("recall_at_k", 0.0)
        ndcg = retrieval_metrics.get("ndcg", retrieval_metrics.get("ndcg@10", 0.0))
        faithfulness = answer_metrics.get("faithfulness", 0.0)
        return round(0.5 * recall + 0.3 * ndcg + 0.2 * faithfulness, 3)


class EvaluationReplyNode(TaskNode):
    """Format evaluation results into a ChatKit-friendly reply."""

    analytics_result_key: str = Field(
        default="analytics_export",
        description="Result entry containing the analytics export payload.",
    )
    ab_testing_result_key: str = Field(
        default="ab_testing",
        description="Result entry containing the A/B testing summary.",
    )
    failure_analysis_result_key: str = Field(
        default="failure_analysis",
        description="Result entry containing failure categories.",
    )
    llm_judge_result_key: str = Field(
        default="llm_judge",
        description="Result entry containing LLM judge results.",
    )
    precision: int = Field(
        default=3,
        ge=0,
        description="Decimal precision for numeric metrics.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Build a summary reply from evaluation results."""
        del config
        results = state.get("results", {}) or {}

        analytics_payload = self.extract_mapping(results, self.analytics_result_key)
        export_payload = self.extract_mapping(analytics_payload, "export")
        metrics_payload = self.extract_mapping(export_payload, "metrics")
        vector_metrics = self.extract_mapping(metrics_payload, "vector_only")
        hybrid_metrics = self.extract_mapping(metrics_payload, "hybrid_fusion")
        answer_metrics = self.extract_mapping(metrics_payload, "answer_quality")

        llm_judge_payload = self.extract_mapping(results, self.llm_judge_result_key)
        ab_testing_payload = self.extract_mapping(results, self.ab_testing_result_key)
        failure_payload = self.extract_mapping(
            results, self.failure_analysis_result_key
        )

        lines = ["Evaluation Results"]
        lines.append(
            f"- Retrieval (vector_only): {self.format_retrieval(vector_metrics)}"
        )
        lines.append(
            f"- Retrieval (hybrid_fusion): {self.format_retrieval(hybrid_metrics)}"
        )
        lines.append(f"- Answer quality: {self.format_answer(answer_metrics)}")
        lines.append(f"- LLM judge: {self.format_llm_judge(llm_judge_payload)}")
        lines.append(f"- A/B test: {self.format_ab_test(ab_testing_payload)}")
        lines.append(
            f"- Failures: {self.format_categories(failure_payload.get('categories'))}"
        )
        feedback_line = self.format_feedback(export_payload)
        if feedback_line:
            lines.append(f"- Feedback: {feedback_line}")

        return {"reply": "\n".join(lines)}

    def extract_mapping(self, payload: Any, key: str) -> dict[str, Any]:
        """Return the nested mapping stored under ``key`` when available."""
        if isinstance(payload, dict):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        return {}

    def format_retrieval(self, metrics: dict[str, Any]) -> str:
        """Format retrieval metric summaries for display."""
        entries = [
            ("Recall@k", metrics.get("recall_at_k")),
            ("MRR", metrics.get("mrr")),
            ("NDCG", metrics.get("ndcg", metrics.get("ndcg@10"))),
            ("MAP", metrics.get("map")),
        ]
        return self.format_pairs(entries)

    def format_answer(self, metrics: dict[str, Any]) -> str:
        """Format answer-quality metric summaries for display."""
        entries = [
            ("Faithfulness", metrics.get("faithfulness")),
            ("Relevance", metrics.get("relevance")),
        ]
        return self.format_pairs(entries)

    def format_llm_judge(self, payload: dict[str, Any]) -> str:
        """Summarize LLM-judge results from the evaluation payload."""
        approved_ratio = payload.get("approved_ratio")
        if isinstance(approved_ratio, int | float):
            return f"approved_ratio={self.format_number(approved_ratio)}"
        return "approved_ratio=n/a"

    def format_ab_test(self, payload: dict[str, Any]) -> str:
        """Summarize A/B test results from the evaluation payload."""
        winner = payload.get("winner")
        rollout_allowed = payload.get("rollout_allowed")
        name = "n/a"
        score_text = "n/a"
        if isinstance(winner, dict):
            if isinstance(winner.get("name"), str):
                name = winner["name"]
            score = winner.get("score")
            if isinstance(score, int | float):
                score_text = self.format_number(score)
        rollout_text = (
            "true"
            if rollout_allowed is True
            else "false"
            if rollout_allowed is False
            else "n/a"
        )
        return f"winner={name}, score={score_text}, rollout_allowed={rollout_text}"

    def format_categories(self, categories: Any) -> str:
        """Format failure categories into a comma-separated list."""
        if isinstance(categories, list):
            values = [str(value) for value in categories if str(value).strip()]
            if values:
                return ", ".join(values)
        return "none"

    def format_feedback(self, payload: dict[str, Any]) -> str | None:
        """Format feedback counts and ratings for display."""
        feedback_count = payload.get("feedback_count")
        average_rating = payload.get("average_rating")
        parts: list[str] = []
        if isinstance(feedback_count, int | float):
            parts.append(f"count={int(feedback_count)}")
        if isinstance(average_rating, int | float):
            parts.append(f"average_rating={self.format_number(average_rating)}")
        if not parts:
            return None
        return ", ".join(parts)

    def format_pairs(self, entries: list[tuple[str, Any]]) -> str:
        """Render numeric label/value pairs in a compact form."""
        parts = []
        for label, value in entries:
            if isinstance(value, int | float):
                parts.append(f"{label}={self.format_number(value)}")
        return ", ".join(parts) if parts else "n/a"

    def format_number(self, value: float) -> str:
        """Format a float using the configured decimal precision."""
        return f"{value:.{self.precision}f}"


def prepare_config_and_stores(
    config: dict[str, Any] | None,
    vector_store: BaseVectorStore | None,
    sparse_vector_store: BaseVectorStore | None,
) -> tuple[dict[str, Any], BaseVectorStore, BaseVectorStore]:
    """Merge configuration overrides and resolve vector store instances."""
    merged_config = merge_dicts(DEFAULT_CONFIG, config or {})
    vector_store_cfg = merged_config["vector_store"]
    sparse_vector_store_cfg = (
        merged_config.get("sparse_vector_store") or vector_store_cfg
    )
    resolved_vector_store = vector_store or build_vector_store_from_config(
        vector_store_cfg
    )
    resolved_sparse_store = sparse_vector_store or build_vector_store_from_config(
        sparse_vector_store_cfg, store_kind="sparse"
    )
    return merged_config, resolved_vector_store, resolved_sparse_store


def build_retrieval_nodes(
    merged_config: dict[str, Any],
    vector_store: BaseVectorStore,
    sparse_vector_store: BaseVectorStore,
) -> dict[str, TaskNode]:
    """Create dataset ingestion, retrieval, and evaluation nodes."""
    dataset_cfg = merged_config["dataset"]
    retrieval_cfg = merged_config["retrieval"]
    fusion_cfg = retrieval_cfg.get("fusion", {})

    dataset_node = DatasetNode(
        name="dataset",
        golden_path=dataset_cfg["golden_path"],
        queries_path=dataset_cfg["queries_path"],
        labels_path=dataset_cfg["labels_path"],
        docs_path=dataset_cfg["docs_path"],
        split=dataset_cfg.get("split"),
        limit=dataset_cfg.get("limit"),
    )
    dense_search = DenseSearchNode(
        name="dense_search",
        vector_store=vector_store,
        embedding_method=retrieval_cfg.get(
            "embedding_method", OPENAI_TEXT_EMBEDDING_3_SMALL
        ),
        top_k=retrieval_cfg.get("top_k", 4),
        query_key="query",
    )
    sparse_search = SparseSearchNode(
        name="sparse_search",
        vector_store=sparse_vector_store,
        embedding_method=retrieval_cfg.get(
            "sparse_embedding_method", PINECONE_BM25_DEFAULT
        ),
        top_k=retrieval_cfg.get("sparse_top_k", retrieval_cfg.get("top_k", 4)),
        vector_store_candidate_k=retrieval_cfg.get("sparse_candidate_k", 50),
        score_threshold=retrieval_cfg.get("sparse_score_threshold", 0.0),
        query_key="query",
    )
    hybrid_fusion = HybridFusionNode(
        name="hybrid_fusion",
        strategy=fusion_cfg.get("strategy", "rrf"),
        rrf_k=fusion_cfg.get("rrf_k", 30),
        top_k=fusion_cfg.get("top_k", 4),
    )
    variant_retrieval = VariantRetrievalNode(
        name="variant_retrieval",
        dense_retriever=dense_search,
        sparse_retriever=sparse_search,
        fusion_node=hybrid_fusion,
    )
    retrieval_to_inputs = ResultToInputsNode(
        name="retrieval_to_inputs",
        source_result_key=variant_retrieval.name,
        mappings={
            "vector_only_results": "vector_only_results",
            "hybrid_results": "hybrid_results",
        },
    )
    retrieval_eval_vector = RetrievalEvaluationNode(
        name="retrieval_eval_vector",
        dataset_key="dataset",
        results_key="vector_only_results",
        k=retrieval_cfg.get("top_k", 4),
    )
    retrieval_eval_hybrid = RetrievalEvaluationNode(
        name="retrieval_eval_hybrid",
        dataset_key="dataset",
        results_key="hybrid_results",
        k=retrieval_cfg.get("top_k", 4),
    )
    metrics_to_inputs = ResultToInputsNode(
        name="metrics_to_inputs",
        source_result_key=retrieval_eval_hybrid.name,
        mappings={"retrieval_metrics": "metrics"},
    )

    return {
        "dataset": dataset_node,
        "variant_retrieval": variant_retrieval,
        "retrieval_to_inputs": retrieval_to_inputs,
        "retrieval_eval_vector": retrieval_eval_vector,
        "retrieval_eval_hybrid": retrieval_eval_hybrid,
        "metrics_to_inputs": metrics_to_inputs,
    }


def build_generation_nodes(
    generation_cfg: dict[str, Any],
) -> dict[str, TaskNode]:
    """Create generation nodes for batched answer production."""
    generator = GroundedGeneratorNode(
        name="grounded_generator",
        context_result_key="generation_context",
        citation_style=generation_cfg.get("citation_style", "inline"),
        ai_model=generation_cfg.get("model"),
    )
    batch_generator = BatchGenerationNode(
        name="batch_generator",
        generator=generator,
        retrieval_key="hybrid_results",
    )
    generation_to_inputs = ResultToInputsNode(
        name="generation_to_inputs",
        source_result_key=batch_generator.name,
        mappings={
            "answers": "answers",
            "conversation_history": "conversation_history",
        },
    )
    return {
        "batch_generator": batch_generator,
        "generation_to_inputs": generation_to_inputs,
    }


def build_feedback_and_analysis_nodes(
    merged_config: dict[str, Any],
) -> dict[str, TaskNode]:
    """Create evaluation, scoring, feedback, and analytics nodes."""
    ab_cfg = merged_config["ab_testing"]
    answer_quality = AnswerQualityEvaluationNode(
        name="answer_quality", references_key="references", answers_key="answers"
    )
    answer_metrics_to_inputs = ResultToInputsNode(
        name="answer_metrics_to_inputs",
        source_result_key=answer_quality.name,
        mappings={"answer_metrics": "metrics"},
    )
    llm_judge = LLMJudgeNode(
        name="llm_judge",
        answers_key="answers",
        min_score=merged_config["llm_judge"].get("min_score", 0.5),
        ai_model=merged_config["llm_judge"].get("model"),
    )
    variant_scoring = VariantScoringNode(name="variant_scoring")
    variant_to_inputs = ResultToInputsNode(
        name="variant_to_inputs",
        source_result_key=variant_scoring.name,
        mappings={
            "variants": "variants",
            "evaluation_metrics": "evaluation_metrics",
        },
    )
    ab_testing = ABTestingNode(
        name="ab_testing",
        primary_metric="score",
        min_metric_threshold=ab_cfg.get("min_metric_threshold", 0.35),
    )
    feedback_synthesis = FeedbackSynthesisNode(name="feedback_synthesis")
    feedback_to_inputs = ResultToInputsNode(
        name="feedback_to_inputs",
        source_result_key=feedback_synthesis.name,
        mappings={"rating": "rating", "comment": "comment"},
    )
    user_feedback = UserFeedbackCollectionNode(name="user_feedback")
    feedback_collection_to_inputs = ResultToInputsNode(
        name="feedback_collection_to_inputs",
        source_result_key=user_feedback.name,
        mappings={"feedback": "feedback"},
    )
    feedback_normalizer = FeedbackNormalizerNode(name="feedback_normalizer")
    feedback_ingestion = FeedbackIngestionNode(name="feedback_ingestion")
    failure_analysis = FailureAnalysisNode(
        name="failure_analysis",
        retrieval_metrics_key="retrieval_metrics",
        answer_metrics_key="answer_metrics",
        feedback_key="feedback",
    )
    analytics_inputs = ResultToInputsNode(
        name="analytics_inputs",
        source_result_key=variant_scoring.name,
        mappings={"metrics": "evaluation_metrics"},
    )
    analytics_export = AnalyticsExportNode(name="analytics_export")
    data_augmentation = DataAugmentationNode(
        name="data_augmentation",
        dataset_key="dataset",
        multiplier=2,
    )
    turn_annotation = TurnAnnotationNode(
        name="turn_annotation", history_key="conversation_history"
    )
    evaluation_reply = EvaluationReplyNode(name="evaluation_reply")
    return {
        "answer_quality": answer_quality,
        "answer_metrics_to_inputs": answer_metrics_to_inputs,
        "llm_judge": llm_judge,
        "variant_scoring": variant_scoring,
        "variant_to_inputs": variant_to_inputs,
        "ab_testing": ab_testing,
        "feedback_synthesis": feedback_synthesis,
        "feedback_to_inputs": feedback_to_inputs,
        "user_feedback": user_feedback,
        "feedback_collection_to_inputs": feedback_collection_to_inputs,
        "feedback_normalizer": feedback_normalizer,
        "feedback_ingestion": feedback_ingestion,
        "failure_analysis": failure_analysis,
        "analytics_inputs": analytics_inputs,
        "analytics_export": analytics_export,
        "data_augmentation": data_augmentation,
        "turn_annotation": turn_annotation,
        "evaluation_reply": evaluation_reply,
    }


async def build_graph(
    *,
    config: dict[str, Any] | None = None,
    vector_store: BaseVectorStore | None = None,
    sparse_vector_store: BaseVectorStore | None = None,
) -> StateGraph:
    """Assemble the evaluation workflow graph described in the design doc.

    Requires the Pinecone index seeded by Demo 1; no in-memory fallback is provided.
    """
    merged_config, vector_store, sparse_vector_store = prepare_config_and_stores(
        config, vector_store, sparse_vector_store
    )
    retrieval_nodes = build_retrieval_nodes(
        merged_config, vector_store, sparse_vector_store
    )
    generation_nodes = build_generation_nodes(merged_config["generation"])
    evaluation_nodes = build_feedback_and_analysis_nodes(merged_config)

    nodes: dict[str, TaskNode] = {
        **retrieval_nodes,
        **generation_nodes,
        **evaluation_nodes,
    }

    workflow = StateGraph(State)
    for node in nodes.values():
        workflow.add_node(node.name, node)

    workflow.set_entry_point(retrieval_nodes["dataset"].name)

    chain = [
        retrieval_nodes["dataset"],
        retrieval_nodes["variant_retrieval"],
        retrieval_nodes["retrieval_to_inputs"],
        retrieval_nodes["retrieval_eval_vector"],
        retrieval_nodes["retrieval_eval_hybrid"],
        generation_nodes["batch_generator"],
        generation_nodes["generation_to_inputs"],
        evaluation_nodes["answer_quality"],
        evaluation_nodes["answer_metrics_to_inputs"],
        evaluation_nodes["llm_judge"],
        evaluation_nodes["variant_scoring"],
        evaluation_nodes["variant_to_inputs"],
        evaluation_nodes["ab_testing"],
        evaluation_nodes["feedback_synthesis"],
        evaluation_nodes["feedback_to_inputs"],
        evaluation_nodes["user_feedback"],
        evaluation_nodes["feedback_collection_to_inputs"],
        evaluation_nodes["feedback_normalizer"],
        evaluation_nodes["feedback_ingestion"],
        retrieval_nodes["metrics_to_inputs"],
        evaluation_nodes["failure_analysis"],
        evaluation_nodes["analytics_inputs"],
        evaluation_nodes["analytics_export"],
        evaluation_nodes["data_augmentation"],
        evaluation_nodes["turn_annotation"],
        evaluation_nodes["evaluation_reply"],
    ]
    for current, nxt in zip(chain, chain[1:], strict=False):
        workflow.add_edge(current.name, nxt.name)
    workflow.add_edge(chain[-1].name, END)

    return workflow
