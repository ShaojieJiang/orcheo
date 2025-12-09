"""Tests for conversational search evaluation and analytics nodes."""

import json
from pathlib import Path
import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.evaluation import (
    ABTestingNode,
    AnalyticsExportNode,
    AnswerQualityEvaluationNode,
    DataAugmentationNode,
    DatasetNode,
    FailureAnalysisNode,
    FeedbackIngestionNode,
    LLMJudgeNode,
    MemoryPrivacyNode,
    PolicyComplianceNode,
    RetrievalEvaluationNode,
    TurnAnnotationNode,
    UserFeedbackCollectionNode,
)


@pytest.mark.asyncio
async def test_dataset_node_filters_split_and_limit() -> None:
    node = DatasetNode(name="dataset")
    state = State(
        inputs={
            "split": "eval",
            "limit": 1,
            "dataset": [
                {"id": "q1", "split": "eval"},
                {"id": "q2", "split": "train"},
            ],
        }
    )

    result = await node.run(state, {})

    assert result["count"] == 1
    assert result["dataset"] == [{"id": "q1", "split": "eval"}]


@pytest.mark.asyncio
async def test_dataset_node_loads_from_files(tmp_path: Path) -> None:
    golden_path = tmp_path / "golden.json"
    queries_path = tmp_path / "queries.json"
    labels_path = tmp_path / "labels.json"
    docs_path = tmp_path / "docs"
    docs_path.mkdir()

    golden_path.write_text(
        json.dumps(
            [
                {
                    "id": "g1",
                    "query": "capital of France",
                    "expected_citations": ["d1"],
                    "expected_answer": "Paris",
                    "split": "test",
                },
            ]
        ),
        encoding="utf-8",
    )
    queries_path.write_text(
        json.dumps([{"id": "q2", "question": "What is Python?", "split": "train"}]),
        encoding="utf-8",
    )
    labels_path.write_text(
        json.dumps([{"query_id": "q2", "doc_id": "d2"}]), encoding="utf-8"
    )
    (docs_path / "d1.md").write_text("Paris is the capital city.", encoding="utf-8")
    (docs_path / "d2.md").write_text("Python is a programming language.", "utf-8")

    node = DatasetNode(
        name="dataset",
        golden_path=str(golden_path),
        queries_path=str(queries_path),
        labels_path=str(labels_path),
        docs_path=str(docs_path),
        split="test",
        limit=1,
    )

    state = State(inputs={})
    result = await node.run(state, {})

    assert result["count"] == 1
    assert result["dataset"][0]["id"] == "g1"
    assert result["references"] == {"g1": "Paris"}
    assert len(result["keyword_corpus"]) == 2
    assert state["inputs"]["dataset"] == result["dataset"]
    assert state["inputs"]["references"] == {"g1": "Paris"}


@pytest.mark.asyncio
async def test_retrieval_evaluation_computes_metrics() -> None:
    node = RetrievalEvaluationNode(name="retrieval_eval", k=3)
    dataset = [
        {"id": "q1", "relevant_ids": ["d1", "d2"]},
        {"id": "q2", "relevant_ids": ["d3"]},
    ]
    retrieval_results = [
        {"query_id": "q1", "results": [{"id": "d1"}, {"id": "d3"}]},
        {"query_id": "q2", "results": [{"id": "d4"}, {"id": "d3"}]},
    ]
    state = State(inputs={"dataset": dataset, "retrieval_results": retrieval_results})

    result = await node.run(state, {})

    metrics = result["metrics"]
    assert metrics["recall_at_k"] > 0.0
    assert metrics["map"] == pytest.approx(0.5)
    assert result["per_query"]["q2"]["mrr"] == 0.5
    assert result["per_query"]["q1"]["map"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_answer_quality_and_judge_nodes_score_answers() -> None:
    references = {"q1": "Paris is the capital of France"}
    answers = [{"id": "q1", "answer": "The capital of France is Paris."}]
    state = State(inputs={"references": references, "answers": answers})

    answer_eval = AnswerQualityEvaluationNode(name="answer_eval")
    judged = await answer_eval.run(state, {})
    assert judged["metrics"]["faithfulness"] > 0.0

    judge = LLMJudgeNode(name="judge", min_score=0.2)
    verdict = await judge.run(state, {})
    assert verdict["approved_ratio"] == 1.0


@pytest.mark.asyncio
async def test_failure_analysis_and_ab_testing_gate_rollout() -> None:
    failure_node = FailureAnalysisNode(name="failures")
    failures = await failure_node.run(
        State(
            inputs={
                "retrieval_metrics": {"recall_at_k": 0.4},
                "answer_metrics": {"faithfulness": 0.9},
                "feedback": [{"rating": 1}],
            }
        ),
        {},
    )
    assert failures["categories"] == ["low_recall", "negative_feedback"]

    ab_node = ABTestingNode(name="ab", min_metric_threshold=0.3)
    ab_result = await ab_node.run(
        State(
            inputs={
                "variants": [
                    {"name": "control", "score": 0.2},
                    {"name": "treatment", "score": 0.8},
                ],
                "evaluation_metrics": {"recall_at_k": 0.6},
                "feedback_score": 0.7,
            }
        ),
        {},
    )

    assert ab_result["winner"]["name"] == "treatment"
    assert ab_result["rollout_allowed"] is True


@pytest.mark.asyncio
async def test_policy_and_memory_privacy_nodes_apply_redactions() -> None:
    policy = PolicyComplianceNode(name="policy")
    policy_result = await policy.run(
        State(
            inputs={"content": "User email test@example.com contains ssn 123-45-6789"}
        ),
        {},
    )
    assert policy_result["violations"]
    assert "[REDACTED_EMAIL]" in policy_result["sanitized"]

    privacy = MemoryPrivacyNode(name="privacy", retention_count=1)
    history = [
        {"role": "user", "content": "My ssn is 123-45-6789", "metadata": {}},
        {"role": "assistant", "content": "Reply", "metadata": {}},
    ]
    privacy_result = await privacy.run(
        State(inputs={"conversation_history": history}), {}
    )
    assert privacy_result["redaction_count"] >= 1
    assert len(privacy_result["sanitized_history"]) == 1


@pytest.mark.asyncio
async def test_augmentation_and_annotations_enrich_examples() -> None:
    augmenter = DataAugmentationNode(name="augment", multiplier=2)
    augmented = await augmenter.run(
        State(inputs={"dataset": [{"query": "origin"}]}), {}
    )
    assert augmented["augmented_count"] == 2
    assert all(entry["augmented"] for entry in augmented["augmented_dataset"])

    annotator = TurnAnnotationNode(name="annotate")
    annotations = await annotator.run(
        State(
            inputs={"conversation_history": [{"role": "user", "content": "Thanks?"}]}
        ),
        {},
    )
    assert annotations["annotations"][0]["is_question"] is True
    assert annotations["annotations"][0]["sentiment"] == "positive"


@pytest.mark.asyncio
async def test_feedback_collection_ingestion_and_export() -> None:
    collector = UserFeedbackCollectionNode(name="collector")
    feedback = await collector.run(
        State(inputs={"rating": 4, "comment": "Nice", "session_id": "s1"}),
        {},
    )
    ingestor = FeedbackIngestionNode(name="ingestor")
    ingestion_result = await ingestor.run(State(inputs=feedback), {})
    assert ingestion_result["ingested"] == 1

    exporter = AnalyticsExportNode(name="exporter")
    exported = await exporter.run(
        State(
            inputs={"metrics": {"recall_at_k": 0.9}, "feedback": [feedback["feedback"]]}
        ),
        {},
    )
    assert exported["export"]["average_rating"] == 4.0
    assert exported["export"]["metrics"]["recall_at_k"] == 0.9


@pytest.mark.asyncio
async def test_dataset_node_rejects_non_list_inputs() -> None:
    node = DatasetNode(name="dataset")
    with pytest.raises(ValueError, match="expects dataset to be a list"):
        await node.run(State(inputs={"dataset": "bad"}), {})


@pytest.mark.asyncio
async def test_dataset_node_skips_split_and_limit_when_invalid() -> None:
    node = DatasetNode(name="dataset")
    dataset = [
        {"id": "q1", "split": "eval"},
        {"id": "q2", "split": "train"},
    ]
    result = await node.run(
        State(inputs={"dataset": dataset, "split": None, "limit": 0}), {}
    )
    assert result["count"] == len(dataset)
    assert result["dataset"] == dataset


@pytest.mark.asyncio
async def test_retrieval_node_requires_list_inputs() -> None:
    node = RetrievalEvaluationNode(name="retrieval")
    with pytest.raises(ValueError, match="retrieval_results lists"):
        await node.run(
            State(inputs={"dataset": [], "retrieval_results": "invalid"}), {}
        )
    with pytest.raises(ValueError, match="retrieval_results lists"):
        await node.run(
            State(inputs={"dataset": "invalid", "retrieval_results": []}), {}
        )


def test_retrieval_metrics_edge_cases() -> None:
    node = RetrievalEvaluationNode(name="retrieval_edge")
    assert node._recall_at_k([], set()) == 0.0
    assert node._mrr(["a"], {"b"}) == 0.0
    assert node._ndcg([], {"relevant"}) == 0.0
    assert node._average_precision(["a"], {"b"}) == 0.0
    assert node._ndcg([], set()) == 0.0
    assert node._average_precision([], set()) == 0.0


@pytest.mark.asyncio
async def test_answer_quality_node_validates_inputs() -> None:
    node = AnswerQualityEvaluationNode(name="answer_eval")
    with pytest.raises(ValueError, match="expects references dict and answers list"):
        await node.run(State(inputs={"references": [], "answers": []}), {})
    with pytest.raises(ValueError, match="expects references dict and answers list"):
        await node.run(
            State(inputs={"references": {"q": "a"}, "answers": "invalid"}), {}
        )


def test_answer_quality_scoring_edge_tokens() -> None:
    node = AnswerQualityEvaluationNode(name="answer_eval")
    assert node._overlap_score("text", "") == 0.0
    assert node._relevance_score("", "reference") == 0.0
    assert node._relevance_score("text", "") == 0.0


@pytest.mark.asyncio
async def test_llm_judge_node_validates_inputs() -> None:
    node = LLMJudgeNode(name="judge")
    with pytest.raises(ValueError, match="expects answers list"):
        await node.run(State(inputs={"answers": {}}), {})


def test_llm_judge_score_and_flags_edge_cases() -> None:
    node = LLMJudgeNode(name="judge", min_score=1.0)
    assert node._score("") == 0.0
    flags = node._flags("This is unsafe ???")
    assert "safety" in flags
    assert "low_confidence" in flags


@pytest.mark.asyncio
async def test_failure_analysis_flags_low_answer_quality() -> None:
    node = FailureAnalysisNode(
        name="failures",
        faithfulness_threshold=0.8,
    )
    result = await node.run(
        State(
            inputs={
                "retrieval_metrics": {"recall_at_k": 0.9},
                "answer_metrics": {"faithfulness": 0.3},
            }
        ),
        {},
    )
    assert result["categories"] == ["low_answer_quality"]


@pytest.mark.asyncio
async def test_ab_testing_node_validates_variants_and_gating() -> None:
    node = ABTestingNode(
        name="ab",
        min_metric_threshold=0.6,
        min_feedback_score=0.5,
    )
    with pytest.raises(ValueError, match="non-empty variants list"):
        await node.run(State(inputs={"variants": []}), {})

    result = await node.run(
        State(
            inputs={
                "variants": [
                    {"name": "winner", "score": 0.8},
                    {"name": "runner", "score": 0.4},
                ],
                "evaluation_metrics": {"recall_at_k": 0.5},
                "feedback_score": 0.3,
            }
        ),
        {},
    )
    assert result["winner"]["name"] == "winner"
    assert result["rollout_allowed"] is False


@pytest.mark.asyncio
async def test_ab_testing_node_skips_optional_checks() -> None:
    node = ABTestingNode(
        name="ab",
        min_metric_threshold=0.5,
    )
    result = await node.run(
        State(
            inputs={
                "variants": [
                    {"name": "solo", "score": 0.7},
                ],
            }
        ),
        {},
    )
    assert result["winner"]["name"] == "solo"
    assert result["rollout_allowed"] is True


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
async def test_analytics_export_validates_feedback_and_counts_categories() -> None:
    exporter = AnalyticsExportNode(name="exporter")
    with pytest.raises(ValueError, match="expects feedback to be a list"):
        await exporter.run(State(inputs={"feedback": {"rating": 5}}), {})

    payload = await exporter.run(
        State(
            inputs={
                "metrics": {"score": 1.0},
                "feedback": [
                    {"rating": 4, "category": "praise"},
                    {"rating": 3, "category": "praise"},
                    {"rating": 5, "category": "issue"},
                ],
            }
        ),
        {},
    )
    assert payload["export"]["feedback_categories"] == {"praise": 2, "issue": 1}
    assert payload["export"]["feedback_count"] == 3


@pytest.mark.asyncio
async def test_policy_compliance_handles_invalid_input_and_detects_violations() -> None:
    node = PolicyComplianceNode(name="policy")
    with pytest.raises(ValueError, match="expects content string"):
        await node.run(State(inputs={"content": 123}), {})

    result = await node.run(
        State(inputs={"content": "password 123-45-6789 contact test@example.com"}), {}
    )
    assert "blocked_term:password" in result["violations"]
    assert "pii:ssn_pattern" in result["violations"]
    assert "pii:email" in result["violations"]
    assert "[REDACTED_TERM]" in result["sanitized"]
    assert "[REDACTED_SSN]" in result["sanitized"]
    assert "[REDACTED_EMAIL]" in result["sanitized"]


def test_policy_compliance_detects_nothing_for_clean_content() -> None:
    node = PolicyComplianceNode(name="policy")
    assert node._detect_violations("Just chatting about cats") == []


@pytest.mark.asyncio
async def test_memory_privacy_requires_list_and_handles_full_history() -> None:
    node = MemoryPrivacyNode(name="privacy")
    with pytest.raises(ValueError, match="expects a list for conversation_history"):
        await node.run(State(inputs={"conversation_history": "bad"}), {})

    history = [{"role": "user", "content": "Reach me at 1234567890", "metadata": {}}]
    result = await node.run(State(inputs={"conversation_history": history}), {})
    assert result["truncated"] is False
    assert result["redaction_count"] >= 1


@pytest.mark.asyncio
async def test_data_augmentation_requires_dataset_list() -> None:
    node = DataAugmentationNode(name="augment")
    with pytest.raises(ValueError, match="expects dataset list"):
        await node.run(State(inputs={"dataset": "bad"}), {})


@pytest.mark.asyncio
async def test_turn_annotation_requires_list_and_sentiment_variants() -> None:
    node = TurnAnnotationNode(name="annotate")
    with pytest.raises(ValueError, match="conversation_history list"):
        await node.run(State(inputs={"conversation_history": "bad"}), {})

    assert node._sentiment("This is terrible") == "negative"
    assert node._sentiment("Neutral text here") == "neutral"
