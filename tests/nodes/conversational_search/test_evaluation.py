import pytest
from langchain_core.runnables import RunnableConfig

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
async def test_dataset_node_returns_metadata() -> None:
    node = DatasetNode(
        name="dataset",
        dataset=[
            {
                "query": "what is orcheo?",
                "relevant_ids": ["d1"],
                "reference_answer": "An orchestration framework.",
            }
        ],
        version="v2",
    )
    state = {"inputs": {}, "results": {}}

    result = await node(state, RunnableConfig())
    payload = result["results"]["dataset"]

    assert payload["metadata"]["size"] == 1
    assert payload["metadata"]["version"] == "v2"
    assert payload["dataset"][0].query == "what is orcheo?"


@pytest.mark.asyncio
async def test_retrieval_evaluation_computes_metrics() -> None:
    dataset = [
        {"query": "q1", "relevant_ids": ["d1", "d3"]},
        {"query": "q2", "relevant_ids": ["x1"]},
    ]
    retrieval_results = [
        {
            "query": "q1",
            "results": [
                {"id": "d1", "score": 1.0},
                {"id": "d2", "score": 0.5},
                {"id": "d3", "score": 0.4},
            ],
        },
        {
            "query": "q2",
            "results": [{"id": "x2", "score": 0.9}, {"id": "x1", "score": 0.8}],
        },
    ]
    state = {
        "inputs": {},
        "results": {
            "dataset": {"dataset": dataset},
            "retrieval_results": {"results": retrieval_results},
        },
    }

    node = RetrievalEvaluationNode(name="retrieval_evaluation", k=3)
    result = await node(state, RunnableConfig())
    metrics = result["results"]["retrieval_evaluation"]["metrics"]

    assert metrics["recall_at_k"] > 0.8
    assert metrics["mrr"] > 0.5
    assert metrics["ndcg"] > 0.7
    assert metrics["map"] > 0.6


@pytest.mark.asyncio
async def test_retrieval_evaluation_handles_single_query_results_list() -> None:
    dataset = [{"query": "what is orcheo?", "relevant_ids": ["d1"]}]
    retrieval_results = [
        {"id": "d1", "score": 0.9},
        {"id": "d2", "score": 0.7},
    ]
    state = {
        "inputs": {},
        "results": {
            "dataset": {"dataset": dataset},
            "retrieval_results": {"results": retrieval_results},
        },
    }

    node = RetrievalEvaluationNode(name="retrieval_evaluation", k=3)
    result = await node(state, RunnableConfig())
    metrics = result["results"]["retrieval_evaluation"]["metrics"]

    assert metrics["recall_at_k"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["ndcg"] == 1.0
    assert metrics["map"] == 1.0


@pytest.mark.asyncio
async def test_answer_quality_scores_overlap_and_faithfulness() -> None:
    dataset = [
        {
            "query": "q1",
            "relevant_ids": ["d1"],
            "reference_answer": "Orcheo is an orchestration framework",
            "context": ["Orcheo is an orchestration framework for AI workflows"],
        }
    ]
    answers = [
        {
            "query": "q1",
            "answer": "Orcheo is an orchestration framework for AI workflows",
            "citations": ["d1"],
        }
    ]
    state = {
        "inputs": {},
        "results": {"dataset": {"dataset": dataset}, "answers": {"answers": answers}},
    }

    node = AnswerQualityEvaluationNode(name="answer_quality")
    result = await node(state, RunnableConfig())
    metrics = result["results"]["answer_quality"]["metrics"]

    assert metrics["faithfulness"] >= 0.5
    assert metrics["overlap"] >= 0.5
    assert metrics["exact_match_rate"] <= 1


@pytest.mark.asyncio
async def test_llm_judge_produces_verdicts() -> None:
    dataset = [
        {
            "query": "q1",
            "relevant_ids": ["d1"],
            "reference_answer": "A framework",
        }
    ]
    answers = [
        {"query": "q1", "answer": "A framework with sources", "citations": ["d1"]}
    ]
    state = {
        "inputs": {},
        "results": {"dataset": {"dataset": dataset}, "answers": {"answers": answers}},
    }

    node = LLMJudgeNode(name="llm_judge", threshold=0.2)
    result = await node(state, RunnableConfig())
    verdicts = result["results"]["llm_judge"]["verdicts"]

    assert verdicts[0]["verdict"] == "pass"
    assert result["results"]["llm_judge"]["average_score"] > 0


@pytest.mark.asyncio
async def test_failure_analysis_flags_low_quality() -> None:
    retrieval_per_query = [
        {"query": "q1", "recall_at_k": 0.2, "mrr": 0.1, "ndcg": 0.2, "map": 0.1}
    ]
    answer_per_query = [
        {"query": "q1", "faithfulness": 0.4, "overlap": 0.3, "exact_match": False}
    ]
    judge_verdicts = [{"query": "q1", "verdict": "fail", "score": 0.1, "reason": ""}]
    state = {
        "inputs": {},
        "results": {
            "retrieval_evaluation": {"per_query": retrieval_per_query},
            "answer_quality": {"per_query": answer_per_query},
            "llm_judge": {"verdicts": judge_verdicts},
        },
    }

    node = FailureAnalysisNode(name="failure_analysis")
    result = await node(state, RunnableConfig())
    failures = result["results"]["failure_analysis"]["failures"]

    assert failures[0]["query"] == "q1"
    assert "low_recall" in failures[0]["failure_modes"]
    assert result["results"]["failure_analysis"]["summary"]["low_recall"] == 1


@pytest.mark.asyncio
async def test_ab_testing_incorporates_feedback_penalty() -> None:
    variants = {"a": {"score": 0.6}, "b": {"score": 0.7}}
    feedback = [{"variant": "b", "sentiment": "negative"}]
    state = {"inputs": {}, "results": {"variants": variants, "feedback": feedback}}

    node = ABTestingNode(name="ab_test", feedback_penalty=0.2)
    result = await node(state, RunnableConfig())
    payload = result["results"]["ab_test"]

    assert payload["winner"] == "a"
    assert payload["variant_scores"]["b"] < payload["variant_scores"]["a"]


@pytest.mark.asyncio
async def test_feedback_collection_and_ingestion() -> None:
    raw_feedback = [
        {"user_id": "u1", "variant": "a", "rating": 5, "comment": "Great"},
        {"user_id": "u2", "variant": "b", "rating": 2, "sentiment": "negative"},
    ]
    collection_node = UserFeedbackCollectionNode(name="feedback")
    state = {"inputs": {"feedback": raw_feedback}, "results": {}}
    collected = await collection_node(state, RunnableConfig())

    feedback_payload = collected["results"]["feedback"]["feedback"]
    assert len(feedback_payload) == 2

    ingestion_state = {"inputs": {}, "results": {"feedback": feedback_payload}}
    ingestion_node = FeedbackIngestionNode(name="ingestion")
    ingested = await ingestion_node(ingestion_state, RunnableConfig())

    assert ingested["results"]["ingestion"]["count"] == 2
    assert (
        ingestion_node.timestamp_field
        in ingested["results"]["ingestion"]["ingested_feedback"][0]
    )


@pytest.mark.asyncio
async def test_analytics_export_combines_sections() -> None:
    state = {
        "inputs": {},
        "results": {
            "retrieval_evaluation": {"metrics": {"recall_at_k": 1.0}},
            "answer_quality": {"metrics": {"faithfulness": 0.9}},
            "llm_judge": {"verdicts": [{"query": "q1", "verdict": "pass"}]},
            "failure_analysis": {"failures": []},
            "feedback": [],
        },
    }

    node = AnalyticsExportNode(name="export")
    result = await node(state, RunnableConfig())
    payload = result["results"]["export"]

    assert payload["retrieval_metrics"]["recall_at_k"] == 1.0
    assert payload["answer_metrics"]["faithfulness"] == 0.9
    assert payload["judge"][0]["verdict"] == "pass"
    assert "exported_at" in payload


@pytest.mark.asyncio
async def test_policy_and_privacy_nodes() -> None:
    policy_node = PolicyComplianceNode(name="policy", blocked_terms=["blocked"])
    policy_state = {
        "inputs": {"answer": "This contains a blocked term."},
        "results": {},
    }
    policy_result = await policy_node(policy_state, RunnableConfig())

    assert policy_result["results"]["policy"]["compliant"] is False

    privacy_node = MemoryPrivacyNode(name="privacy")
    privacy_state = {
        "inputs": {
            "memories": [{"content": "Contact me at test@example.com or +123 456 789."}]
        },
        "results": {},
    }
    privacy_result = await privacy_node(privacy_state, RunnableConfig())

    redacted = privacy_result["results"]["privacy"]["memories"][0]["content"]
    assert "[REDACTED]" in redacted


@pytest.mark.asyncio
async def test_data_augmentation_and_turn_annotation() -> None:
    dataset = [{"query": "q1", "relevant_ids": ["d1"]}]
    aug_state = {"inputs": {}, "results": {"dataset": {"dataset": dataset}}}
    augmentation_node = DataAugmentationNode(name="augment")
    augmented = await augmentation_node(aug_state, RunnableConfig())

    augmented_dataset = augmented["results"]["augment"]["dataset"]
    assert len(augmented_dataset) == 2
    assert any(item.query.endswith("(augmented)") for item in augmented_dataset)

    turns = [{"text": "Hi"}, {"text": "Hello?"}]
    turn_state = {"inputs": {"turns": turns}, "results": {}}
    annotation_node = TurnAnnotationNode(name="turns")
    annotated = await annotation_node(turn_state, RunnableConfig())

    annotated_turns = annotated["results"]["turns"]["turns"]
    assert annotated_turns[0]["role"] == "user"
    assert annotated_turns[1]["intent"] == "question"
