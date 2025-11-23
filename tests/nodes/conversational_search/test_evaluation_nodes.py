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
from orcheo.nodes.conversational_search.models import EvaluationExample, SearchResult


def test_evaluation_example_validation() -> None:
    with pytest.raises(ValueError, match="relevant_ids"):
        EvaluationExample(id="bad", query="q", relevant_ids=[""], reference_answer=None)


@pytest.mark.asyncio
async def test_dataset_node_supports_loader_and_state_overrides() -> None:
    async def loader() -> list[dict[str, str]]:
        return [
            {
                "id": "ex-1",
                "query": "hello?",
                "relevant_ids": ["c1"],
                "reference_answer": "world",
            }
        ]

    node = DatasetNode(name="dataset", dataset_loader=loader)
    state = State(inputs={}, results={}, structured_response=None)

    output = await node.run(state, {})

    assert len(output["dataset"]) == 1
    assert output["dataset"][0].id == "ex-1"

    override_state = State(
        inputs={"dataset": [{"id": "override", "query": "q", "relevant_ids": []}]},
        results={},
        structured_response=None,
    )

    override_output = await node.run(override_state, {})

    assert override_output["dataset"][0].id == "override"


@pytest.mark.asyncio
async def test_dataset_node_requires_payload() -> None:
    node = DatasetNode(name="dataset-empty")
    with pytest.raises(ValueError, match="requires a dataset"):
        await node.run(State(inputs={}, results={}, structured_response=None), {})


@pytest.mark.asyncio
async def test_retrieval_evaluation_computes_metrics() -> None:
    dataset = [
        EvaluationExample(
            id="ex-1", query="q1", relevant_ids=["a", "b"], reference_answer=None
        )
    ]
    retrieval_results = {
        "ex-1": [
            SearchResult(id="a", score=1.0, text="", metadata={}, source="vector"),
            SearchResult(id="c", score=0.5, text="", metadata={}, source="vector"),
        ]
    }
    state = State(
        inputs={},
        results={"dataset": dataset, "retrieval_results": retrieval_results},
        structured_response=None,
    )
    node = RetrievalEvaluationNode(name="retrieval")

    output = await node.run(state, {})

    metrics = output["retrieval_metrics"]
    assert pytest.approx(metrics["recall"], rel=1e-3) == 0.5
    assert pytest.approx(metrics["mrr"], rel=1e-3) == 1.0
    assert metrics["map"] > 0

    node_missing = RetrievalEvaluationNode(name="missing")
    with pytest.raises(ValueError, match="Retrieval results were not provided"):
        await node_missing.run(
            State(inputs={}, results={"dataset": dataset}, structured_response=None), {}
        )


@pytest.mark.asyncio
async def test_answer_quality_and_judge_nodes_score_responses() -> None:
    dataset = [
        EvaluationExample(
            id="ex-1",
            query="question",
            relevant_ids=[],
            reference_answer="hello world",
        )
    ]
    answers = {"ex-1": "hello world"}
    state = State(
        inputs={},
        results={"dataset": dataset, "answers": answers},
        structured_response=None,
    )

    quality_node = AnswerQualityEvaluationNode(name="quality")
    judge_node = LLMJudgeNode(name="judge")

    quality_output = await quality_node.run(state, {})
    judge_output = await judge_node.run(state, {})

    assert quality_output["answer_quality"]["average_f1"] == 1.0
    assert quality_output["answer_quality"]["exact_match_rate"] == 1.0
    assert judge_output["average_score"] >= 1.0

    empty_state = State(
        inputs={},
        results={
            "dataset": [
                EvaluationExample(
                    id="ex-2", query="q", relevant_ids=[], reference_answer=None
                )
            ],
            "answers": {"ex-2": ""},
        },
        structured_response=None,
    )
    empty_output = await quality_node.run(empty_state, {})
    judge_empty = await judge_node.run(empty_state, {})

    assert empty_output["answer_quality"]["average_f1"] == 1.0
    assert judge_empty["average_score"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_failure_analysis_and_ab_testing_surface_findings() -> None:
    results = {
        "retrieval_metrics": {"recall": 0.4, "ndcg": 0.3},
        "answer_quality": {"average_f1": 0.4, "exact_match_rate": 0.1},
        "average_score": 0.2,
        "variant_a": {"average_f1": 0.4},
        "variant_b": {"average_f1": 0.6},
    }
    state = State(inputs={}, results=results, structured_response=None)
    failure_node = FailureAnalysisNode(name="failure")
    ab_test_node = ABTestingNode(name="ab-test")

    failure_output = await failure_node.run(state, {})
    ab_output = await ab_test_node.run(state, {})

    assert failure_output["status"] == "action_required"
    assert "retrieval_recall_low" in failure_output["findings"]
    assert ab_output["winner"] == "b"
    assert pytest.approx(ab_output["score_delta"], rel=1e-3) == 0.2

    clean_results = {
        "retrieval_metrics": {"recall": 0.9, "ndcg": 0.9},
        "answer_quality": {"average_f1": 0.9, "exact_match_rate": 0.9},
        "average_score": 0.9,
        "variant_a": {"average_f1": 0.7},
        "variant_b": {"average_f1": 0.6},
    }
    clean_state = State(inputs={}, results=clean_results, structured_response=None)
    clean_output = await failure_node.run(clean_state, {})
    assert clean_output["status"] == "pass"


@pytest.mark.asyncio
async def test_feedback_collection_ingestion_and_export() -> None:
    dataset = [
        EvaluationExample(
            id="ex-1", query="q", relevant_ids=["a"], reference_answer=None
        )
    ]
    feedback_payload = [
        {"rating": 4, "comment": "good", "user_id": "u1", "tags": ["helpful"]}
    ]
    collection_node = UserFeedbackCollectionNode(name="collect")
    ingestion_node = FeedbackIngestionNode(name="ingest")

    state_collect = State(
        inputs={"feedback": feedback_payload}, results={}, structured_response=None
    )
    collect_output = await collection_node.run(state_collect, {})

    state_ingest = State(
        inputs={},
        results={"dataset": dataset, "feedback": collect_output["feedback"]},
        structured_response=None,
    )
    ingest_output = await ingestion_node.run(state_ingest, {})

    assert ingest_output["ingested_feedback"] == 1
    assert ingest_output["dataset"][0].metadata["user_feedback"]

    captured: dict[str, object] = {}

    def sink(report: dict[str, object]) -> None:
        captured.update(report)

    export_node = AnalyticsExportNode(name="export", sink=sink)
    state_export = State(
        inputs={},
        results={
            "retrieval_metrics": {"recall": 1.0},
            "answer_quality": {"average_f1": 1.0},
            "average_score": 0.9,
            "feedback": collect_output["feedback"],
        },
        structured_response=None,
    )
    export_output = await export_node.run(state_export, {})

    assert export_output["exported"] is True
    assert captured["judge"] == 0.9

    with pytest.raises(ValueError):
        await collection_node.run(
            State(
                inputs={"feedback": [{"rating": 10, "comment": "bad"}]},
                results={},
                structured_response=None,
            ),
            {},
        )

    with pytest.raises(ValueError, match="feedback must be provided as a list"):
        await ingestion_node.run(
            State(
                inputs={},
                results={"dataset": dataset, "feedback": "oops"},
                structured_response=None,
            ),
            {},
        )

    export_no_sink = AnalyticsExportNode(name="export2")
    export_no_sink_output = await export_no_sink.run(state_export, {})
    assert export_no_sink_output["exported"] is False


@pytest.mark.asyncio
async def test_compliance_privacy_augmentation_and_annotations() -> None:
    dataset = [
        EvaluationExample(id="ex-1", query="q", relevant_ids=[], reference_answer="ref")
    ]
    answers = {"ex-1": "contains password"}
    compliance_node = PolicyComplianceNode(name="policy")
    compliance_state = State(
        inputs={}, results={"answers": answers}, structured_response=None
    )
    compliance_output = await compliance_node.run(compliance_state, {})

    assert compliance_output["compliant"] is False
    assert compliance_output["findings"]

    clean_compliance = await compliance_node.run(
        State(inputs={}, results={"answers": {"ex-1": "ok"}}, structured_response=None),
        {},
    )
    assert clean_compliance["compliant"] is True

    privacy_node = MemoryPrivacyNode(name="privacy")
    privacy_state = State(
        inputs={},
        results={"memory": [{"note": "call me at 123-45-6789", "email": "a@b.com"}]},
        structured_response=None,
    )
    privacy_output = await privacy_node.run(privacy_state, {})

    assert privacy_output["redacted_count"] == 2
    assert "[REDACTED]" in privacy_output["sanitized_memory"][0]["note"]

    privacy_clean = await privacy_node.run(
        State(
            inputs={},
            results={"memory": [{"note": "nothing sensitive", "other": 1}]},
            structured_response=None,
        ),
        {},
    )
    assert privacy_clean["redacted_count"] == 0

    augmentation_node = DataAugmentationNode(
        name="augment", augmentation_count=2, prefix="p"
    )
    augmentation_state = State(
        inputs={}, results={"dataset": dataset}, structured_response=None
    )
    augmentation_output = await augmentation_node.run(augmentation_state, {})

    assert augmentation_output["augmentation_count"] == 2
    assert len(augmentation_output["augmented_dataset"]) == 3

    augmentation_zero = await DataAugmentationNode(
        name="augment-zero", augmentation_count=0
    ).run(State(inputs={}, results={"dataset": dataset}, structured_response=None), {})
    assert augmentation_zero["augmentation_count"] == 0

    annotation_node = TurnAnnotationNode(name="annotate")
    conversation = [
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I am fine"},
    ]
    annotation_state = State(
        inputs={"conversation": conversation}, results={}, structured_response=None
    )
    annotation_output = await annotation_node.run(annotation_state, {})

    assert annotation_output["conversation"][0]["annotations"]["is_question"] is True
    assert annotation_output["conversation"][1]["annotations"]["sentiment"] == "neutral"

    with pytest.raises(ValueError, match="conversation must be provided"):
        await annotation_node.run(
            State(inputs={"conversation": "bad"}, results={}, structured_response=None),
            {},
        )
