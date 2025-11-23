import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.models import SearchResult


@pytest.mark.asyncio
async def test_grounded_generator_returns_citations_and_response() -> None:
    context = [
        SearchResult(
            id="chunk-1",
            score=0.9,
            text="orcheo builds graphs",
            metadata={"source": "docs"},
            source="vector",
            sources=["vector"],
        )
    ]
    state = State(
        inputs={"query": "what does orcheo build?"},
        results={"retrieval": {"results": context}},
        structured_response=None,
    )
    node = GroundedGeneratorNode(name="grounded")

    result = await node.run(state, {})

    assert "orcheo builds graphs" in result["response"]
    assert result["citations"] == [
        {
            "id": "1",
            "source_id": "chunk-1",
            "snippet": "orcheo builds graphs",
            "metadata": {"source": "docs"},
            "sources": ["vector"],
        }
    ]
    assert result["tokens_used"] >= 5
    assert result["attempts"] == 1
    assert result["backoff_schedule"] == []


@pytest.mark.asyncio
async def test_grounded_generator_retries_and_applies_backoff() -> None:
    attempts: dict[str, int] = {"count": 0}

    async def flaky_generator(query: str, context: list[SearchResult]) -> str:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("transient failure")
        return f"Recovered answer for {query}"

    state = State(
        inputs={"query": "tell me"},
        results={
            "retrieval": {
                "results": [
                    SearchResult(
                        id="a",
                        score=1.0,
                        text="ctx",
                        metadata={},
                        source="vector",
                        sources=["vector"],
                    )
                ]
            }
        },
        structured_response=None,
    )
    node = GroundedGeneratorNode(
        name="grounded-retry",
        generator=flaky_generator,
        max_retries=3,
        base_delay_seconds=0.0,
        backoff_factor=2.0,
    )

    result = await node.run(state, {})

    assert result["attempts"] == 2
    assert result["backoff_schedule"] == [0.0]
    assert "Recovered answer" in result["response"]


@pytest.mark.asyncio
async def test_grounded_generator_requires_context() -> None:
    state = State(inputs={"query": "hi"}, results={}, structured_response=None)
    node = GroundedGeneratorNode(name="grounded-empty")

    with pytest.raises(
        ValueError, match="GroundedGeneratorNode requires at least one context result"
    ):
        await node.run(state, {})
