import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.evaluation import (
    ABTestingNode,
    AnalyticsExportNode,
    AnswerQualityEvaluationNode,
    DataAugmentationNode,
    DatasetNode,
    FeedbackIngestionNode,
    FailureAnalysisNode,
    LLMJudgeNode,
    MemoryPrivacyNode,
    PolicyComplianceNode,
    RetrievalEvaluationNode,
    TurnAnnotationNode,
    UserFeedbackCollectionNode,
)
from orcheo.nodes.conversational_search.models import SearchResult


@pytest.mark.asyncio
async def test_dataset_node_validates_and_limits_entries() -> None:
    dataset = [
        {
            "query": "orcheo features",
            "relevant_documents": ["doc-1", "doc-2"],
            "reference_answer": "Orcheo provides graphs",
        },
        {
            "query": "another",
            "relevant_documents": ["doc-3"],
            "reference_answer": "Other answer",
        },
    ]
    node = DatasetNode(name="dataset", limit=1)
    state = State(inputs={"dataset": dataset}, results={}, structured_response=None)

    result = await node.run(state, {})

    assert result["size"] == 1
    assert result["dataset"][0]["query"] == "orcheo features"
    assert set(result["fields"]) == {"query", "reference_answer", "relevant_documents"}


@pytest.mark.asyncio
async def test_retrieval_evaluation_computes_metrics() -> None:
    dataset = [
        {
            "query": "orcheo",
            "relevant_documents": ["doc-1", "doc-2"],
            "reference_answer": "Orcheo info",
        }
    ]
    retrievals = [
        {
            "query": "orcheo",
            "results": [
                SearchResult(id="doc-1", score=1.0, text="a", metadata={}),
                SearchResult(id="other", score=0.8, text="b", metadata={}),
                SearchResult(id="doc-2", score=0.7, text="c", metadata={}),
            ],
        }
    ]
    node = RetrievalEvaluationNode(name="retrieval-eval", top_k=3)
    state = State(
        inputs={"dataset": dataset, "retrievals": retrievals},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["recall@k"] == pytest.approx(1.0)
    assert result["mrr"] == pytest.approx(1.0)
    assert result["map"] == pytest.approx(0.833, rel=1e-3)
    assert result["ndcg"] == pytest.approx(0.92, rel=1e-2)
    assert result["per_query"][0]["hits"] == ["doc-1", "doc-2"]


@pytest.mark.asyncio
async def test_answer_quality_and_llm_judge_nodes() -> None:
    dataset = [
        {
            "query": "what is orcheo",
            "relevant_documents": ["doc-1"],
            "reference_answer": "Orcheo is an orchestration engine for graphs",
        }
    ]
    answers = [
        {
            "query": "what is orcheo",
            "answer": "Orcheo is an orchestration engine for graphs with citations [1]",
            "context": ["Orcheo is an orchestration engine"],
        }
    ]

    quality_node = AnswerQualityEvaluationNode(name="answer-eval")
    quality_state = State(
        inputs={"dataset": dataset, "answers": answers},
        results={},
        structured_response=None,
    )
    quality = await quality_node.run(quality_state, {})

    assert quality["faithfulness"] > 0.5
    assert quality["relevance"] > 0.4

    judge_node = LLMJudgeNode(name="judge", passing_score=0.8)
    judge_state = State(
        inputs={
            "answer": answers[0]["answer"],
            "grounding": "Orcheo is an orchestration engine",
        },
        results={},
        structured_response=None,
    )
    verdict = await judge_node.run(judge_state, {})

    assert verdict["verdict"] == "pass"
    assert "Missing explicit citations" not in verdict["reasons"]


@pytest.mark.asyncio
async def test_failure_analysis_and_ab_testing_flow() -> None:
    metrics = {
        "retrieval": {"recall@k": 0.4},
        "answer": {"faithfulness": 0.3},
        "llm_verdict": "fail",
    }
    failure_node = FailureAnalysisNode(name="failure")
    failure_state = State(
        inputs={"metrics": metrics},
        results={},
        structured_response=None,
    )

    failure_result = await failure_node.run(failure_state, {})

    assert not failure_result["passed"]
    assert set(failure_result["failures"]) == {
        "retrieval_failure",
        "answer_quality_failure",
        "llm_judge_failure",
    }

    ab_node = ABTestingNode(name="ab")
    ab_state = State(
        inputs={"variants": {"control": {"score": 0.6}, "treatment": {"score": 0.8}}},
        results={},
        structured_response=None,
    )

    ab_result = await ab_node.run(ab_state, {})

    assert ab_result["winner"] == "treatment"
    assert ab_result["variants_compared"] == 2


@pytest.mark.asyncio
async def test_feedback_collection_and_ingestion_nodes() -> None:
    raw_feedback = [
        {"user": "alice", "rating": 5, "comment": "great", "query": "hello"}
    ]
    collection_node = UserFeedbackCollectionNode(name="collect")
    collection_state = State(
        inputs={"feedback": raw_feedback}, results={}, structured_response=None
    )
    collected = await collection_node.run(collection_state, {})

    assert collected["count"] == 1
    assert collected["feedback"][0]["user"] == "alice"

    ingestion_node = FeedbackIngestionNode(
        name="ingest", existing_feedback=[{"user": "bob"}]
    )
    ingestion_state = State(
        inputs={"feedback": collected["feedback"]},
        results={},
        structured_response=None,
    )

    ingested = await ingestion_node.run(ingestion_state, {})

    assert ingested["total"] == 2
    assert any(entry["user"] == "bob" for entry in ingested["feedback_store"])


@pytest.mark.asyncio
async def test_compliance_and_privacy_nodes() -> None:
    compliance_node = PolicyComplianceNode(name="compliance")
    compliance_state = State(
        inputs={"content": "user shared a password in chat"},
        results={},
        structured_response=None,
    )

    compliance_result = await compliance_node.run(compliance_state, {})

    assert not compliance_result["passed"]
    assert "password" in compliance_result["violations"]

    privacy_node = MemoryPrivacyNode(name="privacy", max_turns=1)
    privacy_state = State(
        inputs={
            "history": [
                {"role": "user", "content": "hi", "metadata": {"email": "a@b.com"}},
                {"role": "assistant", "content": "ok", "metadata": {"topic": "demo"}},
            ]
        },
        results={},
        structured_response=None,
    )

    privacy_result = await privacy_node.run(privacy_state, {})

    assert privacy_result["history"][0]["metadata"] == {"topic": "demo"}
    assert privacy_result["audit_log"]["remaining_turns"] == 1


@pytest.mark.asyncio
async def test_augmentation_annotation_and_export_nodes() -> None:
    dataset = [
        {
            "query": "summarize", 
            "relevant_documents": ["doc-1"],
            "reference_answer": "summary",
        }
    ]
    augmentation_node = DataAugmentationNode(
        name="augment", augmentations_per_example=1
    )
    augmentation_state = State(
        inputs={"dataset": dataset}, results={}, structured_response=None
    )

    augmented = await augmentation_node.run(augmentation_state, {})

    assert augmented["total"] == 2
    assert any(
        example.get("augmentation") for example in augmented["augmented_dataset"]
    )

    annotation_node = TurnAnnotationNode(name="annotate")
    annotation_state = State(
        inputs={"history": [{"role": "user", "content": "feedback?"}]},
        results={},
        structured_response=None,
    )

    annotations = await annotation_node.run(annotation_state, {})

    assert annotations["count"] == 1
    assert annotations["annotated_history"][0]["topic"] == "feedback"

    export_node = AnalyticsExportNode(name="export")
    export_state = State(
        inputs={"metrics": {"recall@k": 1.0}, "feedback": [{"user": "alice"}]},
        results={},
        structured_response=None,
    )

    export_result = await export_node.run(export_state, {})

    assert export_result["feedback_count"] == 1
    assert "generated_at" in export_result["export"]

