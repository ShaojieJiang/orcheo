"""Tests for ConversationalBatchEvalNode."""

from typing import Any
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.evaluation.batch import ConversationalBatchEvalNode


QRECC_CONVERSATIONS = [
    {
        "conversation_id": "conv1",
        "turns": [
            {
                "turn_id": "1",
                "raw_question": "What is Python?",
                "gold_rewrite": "What is the Python programming language?",
                "context": [],
            },
            {
                "turn_id": "2",
                "raw_question": "Who created it?",
                "gold_rewrite": "Who created the Python programming language?",
                "context": ["What is Python?"],
            },
        ],
    },
    {
        "conversation_id": "conv2",
        "turns": [
            {
                "turn_id": "1",
                "raw_question": "What is Java?",
                "gold_rewrite": "What is the Java programming language?",
                "context": [],
            },
        ],
    },
]

MD2D_CONVERSATIONS = [
    {
        "conversation_id": "d1",
        "turns": [
            {
                "turn_id": "0",
                "user_utterance": "How do I apply?",
                "gold_response": "You can apply online.",
            },
            {
                "turn_id": "1",
                "user_utterance": "What documents?",
                "gold_response": "You need proof of identity.",
            },
        ],
    },
]


@pytest.mark.asyncio
async def test_batch_eval_collects_predictions_and_references() -> None:
    node = ConversationalBatchEvalNode(name="batch")
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    result = await node.run(state, {})

    assert result["total_turns"] == 3
    assert result["total_conversations"] == 2
    assert len(result["predictions"]) == 3
    assert len(result["references"]) == 3

    assert result["references"] == [
        "What is the Python programming language?",
        "Who created the Python programming language?",
        "What is the Java programming language?",
    ]


@pytest.mark.asyncio
async def test_batch_eval_passthrough_uses_raw_question() -> None:
    node = ConversationalBatchEvalNode(name="batch")
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    result = await node.run(state, {})

    assert result["predictions"][0] == "What is Python?"
    assert result["predictions"][1] == "Who created it?"
    assert result["predictions"][2] == "What is Java?"


@pytest.mark.asyncio
async def test_batch_eval_uses_prediction_field_when_present() -> None:
    convs = [
        {
            "conversation_id": "conv1",
            "turns": [
                {
                    "turn_id": "1",
                    "raw_question": "original",
                    "gold_rewrite": "gold",
                    "query": "rewritten query",
                },
            ],
        }
    ]
    node = ConversationalBatchEvalNode(name="batch", prediction_field="query")
    state = State(inputs={"conversations": convs})
    result = await node.run(state, {})

    assert result["predictions"] == ["rewritten query"]
    assert result["references"] == ["gold"]


@pytest.mark.asyncio
async def test_batch_eval_per_conversation_breakdown() -> None:
    node = ConversationalBatchEvalNode(name="batch")
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    result = await node.run(state, {})

    per_conv = result["per_conversation"]
    assert "conv1" in per_conv
    assert "conv2" in per_conv
    assert per_conv["conv1"]["num_turns"] == 2
    assert per_conv["conv2"]["num_turns"] == 1
    assert len(per_conv["conv1"]["predictions"]) == 2
    assert len(per_conv["conv2"]["predictions"]) == 1


@pytest.mark.asyncio
async def test_batch_eval_limits_conversations() -> None:
    node = ConversationalBatchEvalNode(name="batch", max_conversations=1)
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    result = await node.run(state, {})

    assert result["total_conversations"] == 1
    assert result["total_turns"] == 2
    assert "conv1" in result["per_conversation"]
    assert "conv2" not in result["per_conversation"]


def test_batch_eval_allows_templated_max_conversations() -> None:
    node = ConversationalBatchEvalNode(
        name="batch",
        max_conversations="{{config.configurable.qrecc.max_conversations}}",
    )
    assert node.max_conversations == "{{config.configurable.qrecc.max_conversations}}"


@pytest.mark.asyncio
async def test_batch_eval_resolves_templated_max_conversations() -> None:
    node = ConversationalBatchEvalNode(
        name="batch",
        max_conversations="{{config.configurable.qrecc.max_conversations}}",
    )
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    node.decode_variables(
        state,
        config={"configurable": {"qrecc": {"max_conversations": 1}}},
    )
    result = await node.run(state, {})
    assert result["total_conversations"] == 1
    assert result["total_turns"] == 2


@pytest.mark.asyncio
async def test_batch_eval_rejects_non_list() -> None:
    node = ConversationalBatchEvalNode(name="batch")
    with pytest.raises(ValueError, match="expects"):
        await node.run(State(inputs={}), {})


@pytest.mark.asyncio
async def test_batch_eval_reads_conversations_from_results() -> None:
    node = ConversationalBatchEvalNode(name="batch")
    state = State(
        inputs={},
        results={"dataset": {"conversations": QRECC_CONVERSATIONS}},
    )
    result = await node.run(state, {})

    assert result["total_turns"] == 3
    assert result["total_conversations"] == 2


@pytest.mark.asyncio
async def test_batch_eval_with_md2d_gold_field() -> None:
    node = ConversationalBatchEvalNode(
        name="batch",
        prediction_field="user_utterance",
        gold_field="gold_response",
    )
    state = State(inputs={"conversations": MD2D_CONVERSATIONS})
    result = await node.run(state, {})

    assert result["total_turns"] == 2
    assert result["predictions"] == ["How do I apply?", "What documents?"]
    assert result["references"] == [
        "You can apply online.",
        "You need proof of identity.",
    ]


@pytest.mark.asyncio
async def test_batch_eval_empty_conversations() -> None:
    node = ConversationalBatchEvalNode(name="batch")
    state: State[str, Any] = State(inputs={"conversations": []})
    result = await node.run(state, {})

    assert result["total_turns"] == 0
    assert result["total_conversations"] == 0
    assert result["predictions"] == []
    assert result["references"] == []


@pytest.mark.asyncio
async def test_batch_eval_builds_history() -> None:
    node = ConversationalBatchEvalNode(name="batch")
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    result = await node.run(state, {})

    conv1 = result["per_conversation"]["conv1"]
    assert conv1["predictions"][0] == "What is Python?"
    assert conv1["predictions"][1] == "Who created it?"


# --- Pipeline mode tests ---


class EchoRewriteNode(TaskNode):
    """Mock pipeline node that uppercases the message."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        inputs = state.get("inputs", {})
        message = inputs.get("message", "")
        return {"query": message.upper()}


class PrefixNode(TaskNode):
    """Mock pipeline node that prepends 'PREFIX:' to the query."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        query = state.get("results", {}).get("rewrite", {}).get("query", "")
        return {"query": f"PREFIX: {query}"}


def _build_pipeline_graph(*nodes: TaskNode) -> StateGraph:
    """Build a linear state graph from ordered task nodes."""
    graph = StateGraph(State)
    for node in nodes:
        graph.add_node(node.name, node)
    graph.set_entry_point(nodes[0].name)
    for index in range(len(nodes) - 1):
        graph.add_edge(nodes[index].name, nodes[index + 1].name)
    graph.add_edge(nodes[-1].name, END)
    return graph


@pytest.mark.asyncio
async def test_batch_eval_pipeline_single_node() -> None:
    """Pipeline with one node: EchoRewriteNode uppercases the query."""
    node = ConversationalBatchEvalNode(
        name="batch",
        prediction_field="query",
        pipeline=_build_pipeline_graph(EchoRewriteNode(name="rewrite")),
    )
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    result = await node.run(state, {})

    assert result["predictions"][0] == "WHAT IS PYTHON?"
    assert result["predictions"][1] == "WHO CREATED IT?"
    assert result["predictions"][2] == "WHAT IS JAVA?"
    assert result["references"] == [
        "What is the Python programming language?",
        "Who created the Python programming language?",
        "What is the Java programming language?",
    ]


@pytest.mark.asyncio
async def test_batch_eval_pipeline_multi_node() -> None:
    """Pipeline with two nodes chained: uppercase then prefix."""
    node = ConversationalBatchEvalNode(
        name="batch",
        prediction_field="query",
        pipeline=_build_pipeline_graph(
            EchoRewriteNode(name="rewrite"),
            PrefixNode(name="prefix"),
        ),
    )
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    result = await node.run(state, {})

    assert result["predictions"][0] == "PREFIX: WHAT IS PYTHON?"
    assert result["predictions"][1] == "PREFIX: WHO CREATED IT?"


@pytest.mark.asyncio
async def test_batch_eval_pipeline_receives_history() -> None:
    """Pipeline nodes receive conversation history in turn state."""
    received_histories: list[list[str]] = []

    class HistoryCapture(TaskNode):
        async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
            inputs = state.get("inputs", {})
            received_histories.append(list(inputs.get("history", [])))
            return {"query": inputs.get("message", "")}

    node = ConversationalBatchEvalNode(
        name="batch",
        prediction_field="query",
        pipeline=_build_pipeline_graph(HistoryCapture(name="capture")),
    )
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    await node.run(state, {})

    # conv1 turn 1: no history
    assert received_histories[0] == []
    # conv1 turn 2: has turn 1's question in history
    assert received_histories[1] == ["What is Python?"]
    # conv2 turn 1: fresh conversation, no history
    assert received_histories[2] == []


@pytest.mark.asyncio
async def test_batch_eval_pipeline_writes_to_state_inputs() -> None:
    """Pipeline mode writes predictions/references to state inputs."""
    node = ConversationalBatchEvalNode(
        name="batch",
        prediction_field="query",
        pipeline=_build_pipeline_graph(EchoRewriteNode(name="rewrite")),
    )
    state = State(inputs={"conversations": QRECC_CONVERSATIONS})
    await node.run(state, {})

    inputs = state.get("inputs", {})
    assert inputs["predictions"] == [
        "WHAT IS PYTHON?",
        "WHO CREATED IT?",
        "WHAT IS JAVA?",
    ]
    assert inputs["references"] == [
        "What is the Python programming language?",
        "Who created the Python programming language?",
        "What is the Java programming language?",
    ]
