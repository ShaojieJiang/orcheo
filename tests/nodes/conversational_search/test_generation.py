import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.triggers.retry import RetryPolicyConfig


def _sample_state(results: dict) -> State:
    return State(
        inputs={"query": "What is orcheo?"}, results=results, structured_response=None
    )


@pytest.mark.asyncio
async def test_grounded_generator_emits_citations_and_tokens() -> None:
    context = [
        SearchResult(
            id="chunk-1",
            score=1.0,
            text="Orcheo ships conversational search primitives.",
            metadata={},
            source="vector",
            sources=["vector"],
        ),
        SearchResult(
            id="chunk-2",
            score=0.8,
            text="GroundedGeneratorNode adds citations to responses.",
            metadata={},
            source="vector",
            sources=["vector"],
        ),
    ]
    state = _sample_state({"retrieval_results": {"results": context}})

    node = GroundedGeneratorNode(name="generator")
    result = await node.run(state, {})

    assert result["citations"][0]["source_id"] == "chunk-1"
    assert result["citations"][1]["source_id"] == "chunk-2"
    assert result["tokens_used"] == len(result["response"].split())
    assert "[1]" in result["response"]


@pytest.mark.asyncio
async def test_grounded_generator_retries_then_succeeds() -> None:
    attempts = {"count": 0}

    async def flaky_generator(prompt: str, context: list[SearchResult]) -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary failure")
        return "Recovered response"

    context = [
        SearchResult(
            id="chunk-3",
            score=1.0,
            text="Reliable context",
            metadata={},
            source="vector",
            sources=["vector"],
        )
    ]
    state = _sample_state({"retrieval_results": {"results": context}})

    retry_policy = RetryPolicyConfig(
        max_attempts=3,
        initial_delay_seconds=0.0,
        backoff_factor=1.0,
        max_delay_seconds=0.0,
        jitter_factor=0.0,
    )

    node = GroundedGeneratorNode(
        name="generator-retry",
        generator=flaky_generator,
        retry_policy=retry_policy,
    )

    result = await node.run(state, {})

    assert attempts["count"] == 2
    assert result["response"] == "Recovered response"
