"""Tests for DatasetNode, QReCCDatasetNode, and MultiDoc2DialDatasetNode."""

import json
from pathlib import Path
from typing import Any
import pytest
from orcheo.graph.state import State
from orcheo.nodes.evaluation.datasets import (
    DatasetNode,
    MultiDoc2DialDatasetNode,
    QReCCDatasetNode,
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


def test_dataset_node_input_helpers_and_update() -> None:
    node = DatasetNode(name="dataset")
    references = {"q1": "answer"}
    keyword_corpus = [{"id": "k1", "content": "payload"}]
    inputs = {
        "references": references,
        "keyword_corpus": keyword_corpus,
    }

    assert node._references_from_inputs(inputs) == references
    assert node._keyword_corpus_from_inputs(inputs) == keyword_corpus

    container: dict[str, Any] = {}
    node._update_inputs(
        container,
        [{"id": "q1"}],
        references,
        keyword_corpus,
        "eval",
        2,
    )
    assert container["split"] == "eval"
    assert container["limit"] == 2


@pytest.mark.asyncio
async def test_dataset_node_validation_and_loading_helpers() -> None:
    node = DatasetNode(name="dataset")
    with pytest.raises(ValueError, match="references to be a dict"):
        node._validate_inputs([{}], references="bad", keyword_corpus=[])

    with pytest.raises(ValueError, match="keyword_corpus to be a list"):
        node._validate_inputs([{}], references={}, keyword_corpus="bad")

    assert node._build_keyword_corpus() == []
    with pytest.raises(ValueError, match="JSON path must be provided"):
        await node._load_json(None)

    node.golden_path = "golden"
    assert node._should_load_from_files(None) is True
    assert node._should_load_from_files([]) is True

    node = DatasetNode(name="dataset")
    with pytest.raises(ValueError, match="golden_path"):
        await node._load_from_files(None, None)


@pytest.mark.asyncio
async def test_dataset_node_loads_json_from_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = DatasetNode(name="dataset", http_timeout=5.0)
    payload = [{"id": "q1"}]
    checked: dict[str, bool] = {"status": False}

    class DummyResponse:
        def raise_for_status(self) -> None:
            checked["status"] = True

        def json(self) -> list[dict[str, str]]:
            return payload

    class DummyClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5.0

        async def __aenter__(self) -> "DummyClient":
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            return None

        async def get(self, url: str) -> DummyResponse:
            assert url == "https://example.com/data.json"
            return DummyResponse()

    monkeypatch.setattr(
        "orcheo.nodes.evaluation.datasets.httpx.AsyncClient",
        DummyClient,
    )

    result = await node._load_json("https://example.com/data.json")
    assert checked["status"] is True
    assert result == payload


# --- QReCCDatasetNode Tests ---


QRECC_SAMPLE = [
    {
        "Conversation_no": 1,
        "Turn_no": 1,
        "Question": "What is Python?",
        "Rewrite": "What is the Python programming language?",
        "Context": [],
        "Answer": "Python is a programming language.",
    },
    {
        "Conversation_no": 1,
        "Turn_no": 2,
        "Question": "Who created it?",
        "Rewrite": "Who created Python?",
        "Context": ["What is Python?", "Python is a programming language."],
        "Answer": "Guido van Rossum.",
    },
    {
        "Conversation_no": 2,
        "Turn_no": 1,
        "Question": "What is Java?",
        "Rewrite": "What is the Java programming language?",
        "Context": [],
        "Answer": "Java is an OOP language.",
    },
]


@pytest.mark.asyncio
async def test_qrecc_dataset_node_parses_conversations() -> None:
    node = QReCCDatasetNode(name="qrecc")
    state = State(inputs={"qrecc_data": QRECC_SAMPLE})
    result = await node.run(state, {})

    assert result["total_conversations"] == 2
    assert result["total_turns"] == 3

    convs = result["conversations"]
    assert len(convs) == 2

    conv1 = convs[0]
    assert conv1["conversation_id"] == "1"
    assert len(conv1["turns"]) == 2
    assert conv1["turns"][0]["raw_question"] == "What is Python?"
    assert (
        conv1["turns"][0]["gold_rewrite"] == "What is the Python programming language?"
    )
    assert conv1["turns"][1]["context"] == [
        "What is Python?",
        "Python is a programming language.",
    ]


@pytest.mark.asyncio
async def test_qrecc_dataset_node_limits_conversations() -> None:
    node = QReCCDatasetNode(name="qrecc", max_conversations=1)
    state = State(inputs={"qrecc_data": QRECC_SAMPLE})
    result = await node.run(state, {})

    assert result["total_conversations"] == 1
    assert len(result["conversations"]) == 1
    assert result["conversations"][0]["conversation_id"] == "1"


@pytest.mark.asyncio
async def test_qrecc_dataset_node_loads_from_file(tmp_path: Path) -> None:
    data_path = tmp_path / "qrecc.json"
    data_path.write_text(json.dumps(QRECC_SAMPLE), encoding="utf-8")

    node = QReCCDatasetNode(name="qrecc", data_path=str(data_path))
    state = State(inputs={})
    result = await node.run(state, {})

    assert result["total_conversations"] == 2
    assert result["total_turns"] == 3


@pytest.mark.asyncio
async def test_qrecc_dataset_node_rejects_non_list() -> None:
    node = QReCCDatasetNode(name="qrecc")
    with pytest.raises(ValueError, match="expects qrecc_data list"):
        await node.run(State(inputs={}), {})


@pytest.mark.asyncio
async def test_qrecc_dataset_node_stores_in_inputs() -> None:
    node = QReCCDatasetNode(name="qrecc")
    state = State(inputs={"qrecc_data": QRECC_SAMPLE})
    await node.run(state, {})

    assert "conversations" in state["inputs"]
    assert len(state["inputs"]["conversations"]) == 2


# --- MultiDoc2DialDatasetNode Tests ---


MD2D_SAMPLE = [
    {
        "dial_id": "d1",
        "domain": "ssa",
        "turns": [
            {
                "turn_id": "0",
                "user_utterance": "How do I apply?",
                "response": "You can apply online.",
                "grounding_spans": [
                    {
                        "doc_id": "doc1",
                        "span_text": "apply online",
                        "start": 10,
                        "end": 22,
                    }
                ],
            },
            {
                "turn_id": "1",
                "user_utterance": "What documents do I need?",
                "response": "You need proof of identity.",
                "grounding_spans": [],
            },
        ],
    },
    {
        "dial_id": "d2",
        "domain": "va",
        "turns": [
            {
                "turn_id": "0",
                "user_utterance": "Am I eligible?",
                "response": "Eligibility depends on service.",
                "grounding_spans": [
                    {
                        "doc_id": "doc2",
                        "span_text": "depends on service",
                        "start": 0,
                        "end": 18,
                    }
                ],
            },
        ],
    },
]


@pytest.mark.asyncio
async def test_md2d_dataset_node_parses_conversations() -> None:
    node = MultiDoc2DialDatasetNode(name="md2d")
    state = State(inputs={"md2d_data": MD2D_SAMPLE})
    result = await node.run(state, {})

    assert result["total_conversations"] == 2
    assert result["total_turns"] == 3

    convs = result["conversations"]
    assert len(convs) == 2

    conv1 = convs[0]
    assert conv1["conversation_id"] == "d1"
    assert conv1["domain"] == "ssa"
    assert len(conv1["turns"]) == 2
    assert conv1["turns"][0]["user_utterance"] == "How do I apply?"
    assert conv1["turns"][0]["gold_response"] == "You can apply online."
    assert len(conv1["turns"][0]["grounding_spans"]) == 1
    assert conv1["turns"][0]["grounding_spans"][0]["doc_id"] == "doc1"


@pytest.mark.asyncio
async def test_md2d_dataset_node_limits_conversations() -> None:
    node = MultiDoc2DialDatasetNode(name="md2d", max_conversations=1)
    state = State(inputs={"md2d_data": MD2D_SAMPLE})
    result = await node.run(state, {})

    assert result["total_conversations"] == 1
    assert len(result["conversations"]) == 1
    assert result["conversations"][0]["conversation_id"] == "d1"


@pytest.mark.asyncio
async def test_md2d_dataset_node_loads_from_file(tmp_path: Path) -> None:
    data_path = tmp_path / "md2d.json"
    data_path.write_text(json.dumps(MD2D_SAMPLE), encoding="utf-8")

    node = MultiDoc2DialDatasetNode(name="md2d", data_path=str(data_path))
    state = State(inputs={})
    result = await node.run(state, {})

    assert result["total_conversations"] == 2
    assert result["total_turns"] == 3


@pytest.mark.asyncio
async def test_md2d_dataset_node_rejects_non_list() -> None:
    node = MultiDoc2DialDatasetNode(name="md2d")
    with pytest.raises(ValueError, match="expects md2d_data list"):
        await node.run(State(inputs={}), {})


@pytest.mark.asyncio
async def test_md2d_dataset_node_stores_in_inputs() -> None:
    node = MultiDoc2DialDatasetNode(name="md2d")
    state = State(inputs={"md2d_data": MD2D_SAMPLE})
    await node.run(state, {})

    assert "conversations" in state["inputs"]
    assert len(state["inputs"]["conversations"]) == 2


@pytest.mark.asyncio
async def test_md2d_dataset_node_handles_missing_fields() -> None:
    sparse_data = [
        {
            "id": "s1",
            "turns": [
                {"user_utterance": "Hello", "response": "Hi"},
            ],
        }
    ]
    node = MultiDoc2DialDatasetNode(name="md2d")
    state = State(inputs={"md2d_data": sparse_data})
    result = await node.run(state, {})

    assert result["total_conversations"] == 1
    conv = result["conversations"][0]
    assert conv["conversation_id"] == "s1"
    assert conv["domain"] == "unknown"
    assert conv["turns"][0]["grounding_spans"] == []
