from __future__ import annotations

import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.conversation import (
    AnswerCachingNode,
    InMemoryMemoryStore,
    MemoryTurn,
    MultiHopPlannerNode,
    SessionManagementNode,
)
from orcheo.nodes.conversational_search.generation import (
    CitationsFormatterNode,
    HallucinationGuardNode,
    StreamingGeneratorNode,
)
from orcheo.nodes.conversational_search.ingestion import IncrementalIndexerNode
from orcheo.nodes.conversational_search.models import DocumentChunk, SearchResult
from orcheo.nodes.conversational_search.retrieval import ReRankerNode, SourceRouterNode
from orcheo.nodes.conversational_search.vector_store import (
    InMemoryVectorStore,
    VectorRecord,
)


@pytest.mark.asyncio
async def test_incremental_indexer_handles_updates_and_deletes() -> None:
    store = InMemoryVectorStore()
    # seed existing record
    store.records["doc-1-chunk-0"] = VectorRecord(
        id="doc-1-chunk-0",
        values=[0.1, 0.2],
        text="original",
        metadata={"__checksum": "seed"},
    )
    store.records["doc-legacy-chunk-0"] = VectorRecord(
        id="doc-legacy-chunk-0",
        values=[0.2],
        text="stale",
        metadata={"__checksum": "legacy"},
    )

    chunks = [
        DocumentChunk(
            id="doc-1-chunk-0",
            document_id="doc-1",
            index=0,
            content="original",  # unchanged relative to checksum: replaced later
            metadata={"document_id": "doc-1", "chunk_index": 0},
        ),
        DocumentChunk(
            id="doc-2-chunk-0",
            document_id="doc-2",
            index=0,
            content="new content",
            metadata={"document_id": "doc-2", "chunk_index": 0},
        ),
    ]

    node = IncrementalIndexerNode(
        name="incremental",
        vector_store=store,
        embedding_function=lambda texts: [
            [float(index)] for index, _ in enumerate(texts)
        ],
    )

    state = State(
        inputs={},
        results={"chunking_strategy": {"chunks": chunks}},
        structured_response=None,
    )

    result = await node.run(state, {})
    assert result["indexed"] == 2
    assert result["deleted"] == ["doc-legacy-chunk-0"]
    assert store.records["doc-2-chunk-0"].metadata["__checksum"]

    # update chunk content to trigger upsert retry path
    chunks[0] = chunks[0].model_copy(update={"content": "updated"})
    state["results"] = {"chunking_strategy": {"chunks": chunks}}
    retried = await node.run(state, {})
    assert retried["indexed"] == 1


@pytest.mark.asyncio
async def test_streaming_generator_retries_and_enforces_backpressure() -> None:
    attempts: dict[str, int] = {"count": 0}

    async def _stream(prompt: str, max_tokens: int, temperature: float):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient")
        if attempts["count"] == 2:
            for _ in range(5):
                yield "overflow "
            return
        for token in ("hello ", "world"):
            yield token

    context = [
        SearchResult(
            id="r1",
            score=1.0,
            text="context",
            metadata={},
            source="vector",
            sources=["vector"],
        )
    ]
    node = StreamingGeneratorNode(
        name="streaming",
        streaming_llm=_stream,
        max_buffer=4,
        max_retries=3,
    )
    state = State(
        inputs={"query": "hi"},
        results={"retriever": {"results": context}},
        structured_response=None,
    )

    result = await node.run(state, {})
    assert result["response"].strip().endswith("[1]")
    assert result["attempts"] == 3
    assert result["segments"] == ["hello ", "world"]


@pytest.mark.asyncio
async def test_hallucination_guard_flags_missing_citations() -> None:
    node = HallucinationGuardNode(name="guard")
    state = State(
        inputs={},
        results={"grounded_generator": {"response": "Answer without sources"}},
        structured_response=None,
    )

    result = await node.run(state, {})
    assert result["status"] == "blocked"
    assert "missing_citations" in result["flags"]
    assert result["route"] == "fallback"


@pytest.mark.asyncio
async def test_reranker_applies_custom_scores() -> None:
    node = ReRankerNode(
        name="reranker",
        scoring_function=lambda result: result.score * 2 + len(result.text),
        top_k=2,
    )
    candidates = [
        SearchResult(
            id="a",
            score=0.2,
            text="alpha",
            metadata={},
            source="vector",
            sources=["vector"],
        ),
        SearchResult(
            id="b",
            score=0.5,
            text="beta beta",
            metadata={},
            source="vector",
            sources=["vector"],
        ),
    ]
    state = State(
        inputs={},
        results={"retriever": {"results": candidates}},
        structured_response=None,
    )

    result = await node.run(state, {})
    assert [entry.id for entry in result["results"]] == ["b", "a"]


@pytest.mark.asyncio
async def test_source_router_matches_keywords_and_defaults() -> None:
    node = SourceRouterNode(
        name="router",
        keyword_routes={"news": ["web"], "docs": ["vector"]},
        default_route=["bm25"],
    )
    state = State(inputs={"query": "latest news"}, results={}, structured_response=None)
    first = await node.run(state, {})
    assert first["route"] == ["web"]

    state["inputs"]["query"] = "unknown"
    fallback = await node.run(state, {})
    assert fallback["route"] == ["bm25"]


@pytest.mark.asyncio
async def test_citations_formatter_normalizes_entries() -> None:
    node = CitationsFormatterNode(name="formatter")
    citations = [
        {"id": "abc", "source_id": "src1", "snippet": "Long text"},
        {"id": "def", "snippet": "Another"},
    ]
    state = State(
        inputs={},
        results={"grounded_generator": {"citations": citations}},
        structured_response=None,
    )

    result = await node.run(state, {})
    assert result["citations"][0]["id"] == "1"
    assert result["citations"][1]["source_id"] == "def"


@pytest.mark.asyncio
async def test_answer_caching_hits_and_expires() -> None:
    clock = {"now": 0.0}

    def tick() -> float:
        return clock["now"]

    node = AnswerCachingNode(name="cache", ttl_seconds=5, time_provider=tick)
    state = State(
        inputs={"query": "What is RAG?"},
        results={"grounded_generator": {"response": "retrieval augmented generation"}},
        structured_response=None,
    )

    miss = await node.run(state, {})
    assert miss["hit"] is False

    clock["now"] += 1
    hit = await node.run(state, {})
    assert hit["hit"] is True

    clock["now"] += 10
    state["results"] = {}  # remove source response to validate expiry miss
    expired = await node.run(state, {})
    assert expired["hit"] is False
    assert expired["response"] is None


@pytest.mark.asyncio
async def test_session_management_clears_on_idle_timeout() -> None:
    clock = {"now": 0.0}

    def tick() -> float:
        return clock["now"]

    memory = InMemoryMemoryStore()
    node = SessionManagementNode(
        name="session",
        memory_store=memory,
        idle_timeout_seconds=5,
        ttl_seconds=20,
        time_provider=tick,
    )

    state = State(inputs={"session_id": "s1"}, results={}, structured_response=None)
    memory.sessions["s1"] = [MemoryTurn(role="user", content="hello")]
    first = await node.run(state, {})
    assert first["cleared"] is False

    clock["now"] += 6
    cleared = await node.run(state, {})
    assert cleared["idle_expired"] is True
    assert "s1" not in memory.sessions


@pytest.mark.asyncio
async def test_multi_hop_planner_respects_limits() -> None:
    node = MultiHopPlannerNode(name="planner", max_hops=2, max_total_tokens=10)
    state = State(
        inputs={"query": "Find capital and population and GDP"},
        results={},
        structured_response=None,
    )

    plan = await node.run(state, {})
    assert plan["total_steps"] <= 2
    assert plan["truncated"] is True
