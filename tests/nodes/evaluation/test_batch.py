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


def test_batch_eval_validate_max_conversations_none() -> None:
    """None max_conversations passes validation (default)."""
    node = ConversationalBatchEvalNode(name="batch", max_conversations=None)
    assert node.max_conversations is None


def test_batch_eval_validate_max_conversations_invalid_string() -> None:
    """Non-integer, non-template string raises ValueError."""
    with pytest.raises(ValueError, match="must be an integer"):
        ConversationalBatchEvalNode(name="batch", max_conversations="bad")


@pytest.mark.asyncio
async def test_batch_eval_resolve_max_conversations_invalid_string() -> None:
    """String that can't resolve to int raises ValueError at runtime."""
    node = ConversationalBatchEvalNode(
        name="batch",
        max_conversations="{{config.configurable.max}}",
    )
    # Simulate template not resolved (stays as string)
    node.max_conversations = "not_a_number"
    with pytest.raises(ValueError, match="must resolve to an integer"):
        await node.run(State(inputs={"conversations": QRECC_CONVERSATIONS}), {})


@pytest.mark.asyncio
async def test_batch_eval_resolve_max_conversations_less_than_one() -> None:
    """max_conversations < 1 raises ValueError."""
    node = ConversationalBatchEvalNode(name="batch", max_conversations=0)
    with pytest.raises(ValueError, match="must be >= 1"):
        await node.run(State(inputs={"conversations": QRECC_CONVERSATIONS}), {})


@pytest.mark.asyncio
async def test_batch_eval_resolves_conversations_from_direct_results() -> None:
    """Conversations found directly in results under conversations_key."""
    node = ConversationalBatchEvalNode(name="batch")
    state = State(
        inputs={},
        results={"conversations": QRECC_CONVERSATIONS},
    )
    result = await node.run(state, {})

    assert result["total_conversations"] == 2
    assert result["total_turns"] == 3


@pytest.mark.asyncio
async def test_batch_eval_fallback_when_no_conversations_found() -> None:
    """When conversations not in inputs, direct results, or nested results."""
    node = ConversationalBatchEvalNode(name="batch")
    state = State(
        inputs={},
        results={"other": {"some_key": "value"}},
    )
    with pytest.raises(ValueError, match="expects conversations list"):
        await node.run(state, {})


def test_batch_eval_extract_prediction_non_mapping() -> None:
    """_extract_prediction returns fallback for non-Mapping result."""
    node = ConversationalBatchEvalNode(name="batch")
    assert node._extract_prediction("not a mapping", "fallback") == "fallback"


def test_batch_eval_extract_prediction_from_top_level() -> None:
    """_extract_prediction finds prediction at top level of result."""
    node = ConversationalBatchEvalNode(name="batch", prediction_field="query")
    result = node._extract_prediction({"query": "found it"}, "fallback")
    assert result == "found it"


def test_batch_eval_extract_prediction_from_results_values() -> None:
    """_extract_prediction searches reversed results values."""
    node = ConversationalBatchEvalNode(name="batch", prediction_field="query")
    result_state = {
        "results": {
            "node_a": {"other": "data"},
            "node_b": {"query": "from node_b"},
        }
    }
    result = node._extract_prediction(result_state, "fallback")
    assert result == "from node_b"


def test_batch_eval_extract_prediction_from_inputs() -> None:
    """_extract_prediction falls back to inputs mapping."""
    node = ConversationalBatchEvalNode(name="batch", prediction_field="query")
    result_state = {
        "results": {"node_a": {"other": "data"}},
        "inputs": {"query": "from inputs"},
    }
    result = node._extract_prediction(result_state, "fallback")
    assert result == "from inputs"


def test_batch_eval_extract_prediction_ultimate_fallback() -> None:
    """_extract_prediction returns fallback when nothing found anywhere."""
    node = ConversationalBatchEvalNode(name="batch", prediction_field="query")
    result_state = {
        "results": {"node_a": {"other": "data"}},
        "inputs": {"other": "data"},
    }
    result = node._extract_prediction(result_state, "fallback")
    assert result == "fallback"


@pytest.mark.asyncio
async def test_batch_eval_resolves_from_nested_results_iteration() -> None:
    """Conversations found in nested results via iteration over values."""
    node = ConversationalBatchEvalNode(name="batch")
    state = State(
        inputs={},
        results={
            "other_node": {"conversations": QRECC_CONVERSATIONS},
        },
    )
    result = await node.run(state, {})

    assert result["total_conversations"] == 2


def test_batch_eval_extract_prediction_skips_non_mapping_results_values() -> None:
    """_extract_prediction skips non-Mapping entries in results values."""
    node = ConversationalBatchEvalNode(name="batch", prediction_field="query")
    result_state: dict[str, Any] = {
        "results": {
            "node_a": "not_a_mapping",
            "node_b": {"query": "found"},
        },
    }
    result = node._extract_prediction(result_state, "fallback")
    assert result == "found"


def test_batch_eval_extract_prediction_inputs_fallback_no_match() -> None:
    """_extract_prediction checks inputs but field not present, uses fallback."""
    node = ConversationalBatchEvalNode(name="batch", prediction_field="query")
    result_state: dict[str, Any] = {
        "results": {},
        "inputs": {"message": "no query field"},
    }
    result = node._extract_prediction(result_state, "fallback")
    assert result == "fallback"
