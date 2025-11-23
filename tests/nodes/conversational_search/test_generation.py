import asyncio
import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.models import SearchResult


def _state_with_context(query: str) -> State:
    results = {
        "retriever": {
            "results": [
                SearchResult(
                    id="chunk-1",
                    score=0.9,
                    text="Orcheo ships modular nodes for RAG workflows.",
                    metadata={"page": 1},
                    source="vector",
                ),
                SearchResult(
                    id="chunk-2",
                    score=0.8,
                    text="Grounded answers include citations.",
                    metadata={"page": 2},
                    source="bm25",
                ),
            ]
        }
    }
    return State(inputs={"query": query}, results=results, structured_response=None)


@pytest.mark.asyncio
async def test_grounded_generator_appends_citations() -> None:
    node = GroundedGeneratorNode(name="generator")
    state = _state_with_context("What does Orcheo provide?")

    result = await node.run(state, {})

    assert result["citations"]
    assert "[1]" in result["response"]
    assert result["tokens_used"] > 0


@pytest.mark.asyncio
async def test_grounded_generator_resolves_context_from_results_field() -> None:
    node = GroundedGeneratorNode(name="generator", context_result_key="hybrid")
    source_state = _state_with_context("How are citations handled?")
    retrieval_results = source_state["results"]["retriever"]["results"]
    state = State(
        inputs=source_state["inputs"],
        results={"results": retrieval_results, "hybrid": {}},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["citations"][0]["source_id"] == "chunk-1"


@pytest.mark.asyncio
async def test_grounded_generator_retries_on_failure() -> None:
    attempts: list[int] = []

    async def flaky_llm(prompt: str, max_tokens: int, temperature: float) -> str:
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("temporary")
        return f"{prompt} stable"

    node = GroundedGeneratorNode(
        name="generator", llm=flaky_llm, max_retries=1, backoff_seconds=0
    )
    state = _state_with_context("Explain citations")

    result = await node.run(state, {})

    assert len(attempts) == 2
    assert "stable" in result["response"]


@pytest.mark.asyncio
async def test_grounded_generator_requires_query_and_context() -> None:
    node = GroundedGeneratorNode(name="generator")
    empty_state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="GroundedGeneratorNode requires a non-empty query string"
    ):
        await node.run(empty_state, {})

    state = State(inputs={"query": "hi"}, results={}, structured_response=None)
    with pytest.raises(
        ValueError, match="GroundedGeneratorNode requires at least one context document"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_grounded_generator_rejects_non_list_context_payload() -> None:
    node = GroundedGeneratorNode(name="generator")
    state = State(
        inputs={"query": "hi"},
        results={"retriever": {"results": "not-a-list"}},
        structured_response=None,
    )

    with pytest.raises(
        ValueError, match="Context payload must be a list of retrieval results"
    ):
        await node.run(state, {})
