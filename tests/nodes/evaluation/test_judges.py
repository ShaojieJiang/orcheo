"""Tests for LLMJudgeNode, FailureAnalysisNode, and ABTestingNode."""

import json
import sys
import types
from typing import Any
import pytest
from orcheo.graph.state import State
from orcheo.nodes.evaluation.judges import (
    ABTestingNode,
    FailureAnalysisNode,
    LLMJudgeNode,
)


@pytest.mark.asyncio
async def test_judge_scores_answers() -> None:
    answers = [{"id": "q1", "answer": "The capital of France is Paris."}]
    state = State(inputs={"answers": answers})

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
async def test_llm_judge_uses_model_response(monkeypatch: pytest.MonkeyPatch) -> None:
    node = LLMJudgeNode(name="judge", ai_model="fake-model", min_score=0.5)

    class DummyResponse:
        def __init__(self) -> None:
            self.content = json.dumps({"score": 0.9, "flags": ["low_confidence"]})

    class DummyModel:
        async def ainvoke(self, messages: list[Any]) -> DummyResponse:
            return DummyResponse()

    def fake_init(model_name: str, **kwargs: Any) -> DummyModel:
        return DummyModel()

    fake_chat_models = types.ModuleType("langchain.chat_models")
    fake_chat_models.init_chat_model = fake_init
    monkeypatch.setitem(sys.modules, "langchain.chat_models", fake_chat_models)

    def fake_message_factory(*, content: str) -> types.SimpleNamespace:
        return types.SimpleNamespace(content=content)

    fake_messages = types.ModuleType("langchain_core.messages")
    fake_messages.SystemMessage = fake_message_factory
    fake_messages.HumanMessage = fake_message_factory
    monkeypatch.setitem(sys.modules, "langchain_core.messages", fake_messages)

    state = State(inputs={"answers": [{"id": "q1", "answer": "Hello"}]})
    result = await node.run(state, {})

    assert result["approved_ratio"] == 1.0
    assert result["verdicts"][0]["flags"] == ["low_confidence"]


def test_llm_judge_parse_model_response_variations() -> None:
    node = LLMJudgeNode(name="judge")
    json_response = types.SimpleNamespace(
        content=json.dumps({"score": 0.42, "flags": ["safety"]})
    )
    score, flags = node._parse_model_response(json_response, "fallback")
    assert score == pytest.approx(0.42)
    assert flags == ["safety"]

    dict_response = {"content": "score 0.33"}
    score, flags = node._parse_model_response(dict_response, "fallback")
    assert score == pytest.approx(0.33)
    assert flags == []

    fallback_content = "unsafe text ???"
    score, flags = node._parse_model_response("no digits", fallback_content)
    assert score == node._score(fallback_content)
    assert "low_confidence" in flags
    assert "safety" in flags


def test_llm_judge_parse_model_response_handles_non_string_content() -> None:
    node = LLMJudgeNode(name="judge")

    class JsonContent:
        def __str__(self) -> str:
            return json.dumps({"score": 0.25, "flags": ["low_confidence"]})

    response = types.SimpleNamespace(content=JsonContent())
    score, flags = node._parse_model_response(response, "fallback")
    assert score == pytest.approx(0.25)
    assert flags == ["low_confidence"]


def test_llm_judge_parse_model_response_handles_dict_input_json() -> None:
    node = LLMJudgeNode(name="judge")
    dict_response = {"content": json.dumps({"score": 0.66, "flags": ["safety"]})}
    score, flags = node._parse_model_response(dict_response, "fallback")
    assert score == pytest.approx(0.66)
    assert flags == ["safety"]


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
async def test_ab_testing_node_handles_nested_evaluation_metrics() -> None:
    node = ABTestingNode(name="ab", min_metric_threshold=0.5)
    result = await node.run(
        State(
            inputs={
                "variants": [
                    {"name": "variant_a", "score": 0.8},
                    {"name": "variant_b", "score": 0.4},
                ],
                "evaluation_metrics": {
                    "variant_a": {"recall_at_k": 0.6, "ndcg": 0.45},
                    "variant_b": {"recall_at_k": 0.4, "ndcg": 0.3},
                },
            }
        ),
        {},
    )

    assert result["winner"]["name"] == "variant_a"
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


def test_ab_testing_normalize_evaluation_metrics_branches() -> None:
    node = ABTestingNode(name="ab", primary_metric="recall")
    assert node._normalize_evaluation_metric({"recall": 0.75}) == 0.75
    assert node._normalize_evaluation_metric(0.8) == 0.8
    node.primary_metric = "score"
    assert node._normalize_evaluation_metric({"score": 0.65}) == 0.65
    assert node._normalize_evaluation_metric({"precision": 0.3, "f1": 0.7}) == 0.7


def test_ab_testing_normalize_evaluation_metric_score_candidate_and_candidates() -> (
    None
):
    node = ABTestingNode(name="ab", primary_metric="precision")
    assert node._normalize_evaluation_metric({"score": 0.55}) == 0.55

    node.primary_metric = "other_metric"
    assert node._normalize_evaluation_metric({"alpha": 0.2, "beta": 0.9}) == 0.9


@pytest.mark.asyncio
async def test_ab_testing_node_rollout_with_metrics_and_feedback() -> None:
    node = ABTestingNode(
        name="ab",
        min_metric_threshold=0.5,
        min_feedback_score=0.4,
    )
    result = await node.run(
        State(
            inputs={
                "variants": [
                    {"name": "alpha", "score": 0.8},
                ],
                "evaluation_metrics": {"alpha": {"score": 0.6}},
                "feedback_score": 0.45,
            }
        ),
        {},
    )

    assert result["winner"]["name"] == "alpha"
    assert result["rollout_allowed"] is True


@pytest.mark.asyncio
async def test_ab_testing_node_evaluation_metrics_gate_rollout() -> None:
    node = ABTestingNode(name="ab", min_metric_threshold=0.7)
    result = await node.run(
        State(
            inputs={
                "variants": [{"name": "alpha", "score": 0.9}],
                "evaluation_metrics": {
                    "alpha": {"score": 0.65},
                    "beta": {"precision": 0.8},
                },
            }
        ),
        {},
    )

    assert result["winner"]["name"] == "alpha"
    assert result["rollout_allowed"] is False
