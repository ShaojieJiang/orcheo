import pytest
from orcheo.nodes.conversational_search.generation import StreamingGeneratorNode
from orcheo.nodes.conversational_search.guardrails import (
    CitationsFormatterNode,
    HallucinationGuardNode,
    ReRankerNode,
    SourceRouterNode,
)
from orcheo.nodes.conversational_search.ingestion import IncrementalIndexerNode
from orcheo.nodes.conversational_search.models import DocumentChunk, SearchResult
from orcheo.nodes.conversational_search.optimization import (
    AnswerCachingNode,
    MultiHopPlannerNode,
    SessionManagementNode,
)
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


pytestmark = pytest.mark.asyncio


class FlakyVectorStore(InMemoryVectorStore):
    failures: int = 1

    async def upsert(self, records):
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("temporary failure")
        await super().upsert(records)


async def test_incremental_indexer_batches_and_retries():
    chunks = [
        DocumentChunk(
            id=f"chunk-{index}",
            document_id="doc",
            index=index,
            content=f"text {index}",
        )
        for index in range(3)
    ]
    state = {
        "results": {
            "chunking_strategy": {"chunks": [chunk.model_dump() for chunk in chunks]}
        }
    }
    vector_store = FlakyVectorStore()
    node = IncrementalIndexerNode(
        name="incremental_indexer",
        vector_store=vector_store,
        batch_size=2,
        max_retries=1,
        backoff_seconds=0,
    )

    result = await node.run(state, config={})
    assert result["indexed"] == 3
    assert len(vector_store.records) == 3

    second = await node.run(state, config={})
    assert second["indexed"] == 0
    assert second["skipped"] == 3


async def test_streaming_generator_retries_and_backpressure():
    class FlakyStreamer:
        def __init__(self):
            self.calls = 0

        async def __call__(self, prompt: str, max_tokens: int, temperature: float):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("boom")
            return ["token", "stream"]

    node = StreamingGeneratorNode(
        name="streaming_generator",
        llm_streamer=FlakyStreamer(),
        max_retries=1,
        backoff_seconds=0,
    )

    result = await node.run({"inputs": {"query": "hello"}}, config={})
    assert result["chunks"] == ["token", "stream"]

    overflowing = StreamingGeneratorNode(
        name="overflowing_generator",
        llm_streamer=lambda *args, **kwargs: ["one", "two", "three", "four"],
        max_buffer_size=3,
    )
    with pytest.raises(OverflowError):
        await overflowing.run({"inputs": {"query": "hi"}}, config={})


async def test_hallucination_guard_detects_missing_citations():
    node = HallucinationGuardNode(name="guard")
    payload = {
        "results": {
            "grounded_generator": {
                "response": "Here is the answer",
                "citations": [{"id": "1", "source": "vector"}],
            }
        }
    }
    result = await node.run(payload, config={})
    assert result["status"] == "flagged"
    assert result["route"] == node.fallback_route


async def test_reranker_and_router_workflow():
    results = [
        SearchResult(id="a", score=0.2, text="a", source="bm25"),
        SearchResult(id="b", score=0.9, text="b", source="vector"),
    ]
    reranker = ReRankerNode(name="reranker", scorer=lambda item: -item.score)
    reranked = await reranker.run({"results": {"results": results}}, config={})
    assert reranked["results"][0].id == "a"

    router = SourceRouterNode(
        name="router",
        routing_table={"bm25": "sparse", "vector": "dense"},
        default_route="dense",
    )
    routing = await router.run(reranked, config={})
    assert routing["route"] == "sparse"
    assert routing["source"] == "bm25"


async def test_citations_formatter_structures_entries():
    results = [
        SearchResult(
            id="1",
            score=1.0,
            text="A long passage about Orcheo",
            metadata={"url": "https://example.com", "title": "Example"},
            sources=["vector"],
        )
    ]
    node = CitationsFormatterNode(name="citations")
    formatted = await node.run({"results": results}, config={})
    assert formatted["citations"][0]["url"] == "https://example.com"
    assert formatted["citations"][0]["title"] == "Example"


async def test_answer_caching_retrieves_from_cache():
    node = AnswerCachingNode(name="cache")
    miss_state = {
        "inputs": {"query": "What is Orcheo?"},
        "results": {"grounded_generator": {"response": "A framework"}},
    }
    first = await node.run(miss_state, config={})
    assert not first["cached"]

    hit_state = {"inputs": {"query": "What is Orcheo?"}, "results": {}}
    second = await node.run(hit_state, config={})
    assert second["cached"]
    assert second["response"] == "A framework"


async def test_session_management_enforces_limits():
    node = SessionManagementNode(name="session", max_sessions=1)
    first = await node.run({"inputs": {"session_id": "s1"}}, config={})
    assert first["allowed"]

    second = await node.run({"inputs": {"session_id": "s2"}}, config={})
    assert "s1" in second["evicted"]


async def test_multihop_planner_truncates_hops():
    node = MultiHopPlannerNode(name="planner", max_hops=2)
    plan = await node.run({"inputs": {"query": "Find A and B and C"}}, config={})
    assert plan["hop_count"] == 2
