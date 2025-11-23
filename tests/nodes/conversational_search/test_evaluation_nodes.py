"""Tests for conversational search evaluation and analytics nodes."""

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
    assert result["per_query"]["q2"]["mrr"] == 0.5


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
