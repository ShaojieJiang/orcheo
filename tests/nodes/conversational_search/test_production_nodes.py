import time
import pytest
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.conversation import InMemoryMemoryStore
from orcheo.nodes.conversational_search.models import DocumentChunk, SearchResult
from orcheo.nodes.conversational_search.production import (
    AnswerCachingNode,
    CitationsFormatterNode,
    HallucinationGuardNode,
    IncrementalIndexerNode,
    MultiHopPlannerNode,
    ReRankerNode,
    SessionManagementNode,
    SourceRouterNode,
    StreamingGeneratorNode,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
)


class FlakyVectorStore(InMemoryVectorStore):
    failures: int = 1

    async def upsert(self, records) -> None:  # type: ignore[override]
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("transient failure")
        await super().upsert(records)


@pytest.mark.asyncio
async def test_incremental_indexer_retries_and_skips_duplicates() -> None:
    store = FlakyVectorStore()
    chunks = [
        DocumentChunk(
            id="chunk-1",
            document_id="doc-1",
            index=0,
            content="first chunk",
            metadata={"page": 1},
        ),
        DocumentChunk(
            id="chunk-2",
            document_id="doc-2",
            index=0,
            content="second chunk",
            metadata={"page": 2},
        ),
    ]
    node = IncrementalIndexerNode(
        name="indexer",
        vector_store=store,
        max_retries=1,
        backoff_seconds=0.0,
    )
    state = State(
        inputs={},
        results={"chunking_strategy": {"chunks": chunks}},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["indexed_count"] == 2
    assert result["skipped"] == 0

    second_result = await node.run(state, {})

    assert second_result["indexed_count"] == 0
    assert second_result["skipped"] == 2
    assert len(store.records) == 2


@pytest.mark.asyncio
async def test_incremental_indexer_raises_after_exhausting_retries() -> None:
    store = FlakyVectorStore(failures=3)
    chunk = DocumentChunk(
        id="chunk-err",
        document_id="doc",
        index=0,
        content="content",
        metadata={},
    )
    node = IncrementalIndexerNode(
        name="indexer-error",
        vector_store=store,
        max_retries=0,
        backoff_seconds=0.0,
    )
    state = State(inputs={}, results={"chunks": [chunk]}, structured_response=None)

    with pytest.raises(RuntimeError, match="upsert failed after retries"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_incremental_indexer_validates_inputs() -> None:
    node = IncrementalIndexerNode(
        name="indexer-empty", vector_store=InMemoryVectorStore()
    )
    empty_state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="IncrementalIndexerNode requires at least one chunk"
    ):
        await node.run(empty_state, {})

    async def bad_embed(texts: list[str]) -> list[str]:
        return ["invalid"]

    chunk = DocumentChunk(
        id="c-1", document_id="d-1", index=0, content="text", metadata={}
    )
    node_bad = IncrementalIndexerNode(
        name="indexer-bad",
        vector_store=InMemoryVectorStore(),
        embedding_function=bad_embed,
    )
    bad_state = State(inputs={}, results={"chunks": [chunk]}, structured_response=None)

    with pytest.raises(ValueError, match="Embedding function must return"):
        await node_bad.run(bad_state, {})


class ListRecordStore(BaseVectorStore):
    records: list[str] = Field(default_factory=list)

    async def upsert(self, records) -> None:  # type: ignore[override]
        self.records.append("done")

    async def search(self, query, top_k=10, filter_metadata=None):  # type: ignore[override]
        return []


@pytest.mark.asyncio
async def test_incremental_indexer_handles_invalid_payloads_and_record_check() -> None:
    node = IncrementalIndexerNode(
        name="indexer-invalid", vector_store=InMemoryVectorStore()
    )
    with pytest.raises(ValueError, match="chunks payload must be a list"):
        await node.run(
            State(inputs={}, results={"chunks": "bad"}, structured_response=None), {}
        )

    chunk = DocumentChunk(
        id="c-unchanged", document_id="doc-1", index=0, content="body", metadata={}
    )
    node_skip = IncrementalIndexerNode(
        name="indexer-weird", vector_store=ListRecordStore(), skip_unchanged=True
    )
    result = await node_skip.run(
        State(inputs={}, results={"chunks": [chunk]}, structured_response=None), {}
    )

    assert result["indexed_count"] == 1


@pytest.mark.asyncio
async def test_streaming_generator_truncates_and_chunks_tokens() -> None:
    calls = {"count": 0}

    async def flaky(prompt: str, max_tokens: int, temperature: float) -> str:
        del max_tokens, temperature
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        return "one two three four"

    node = StreamingGeneratorNode(
        name="stream",
        llm=flaky,
        max_retries=1,
        backoff_seconds=0.0,
        chunk_size=2,
        buffer_limit=3,
    )
    state = State(inputs={"prompt": "start"}, results={}, structured_response=None)

    result = await node.run(state, {})

    assert result["token_count"] == 3
    assert result["truncated"] is True
    assert all(frame["size"] <= 2 for frame in result["frames"])


@pytest.mark.asyncio
async def test_streaming_generator_uses_default_llm() -> None:
    node = StreamingGeneratorNode(
        name="stream-default", buffer_limit=None, chunk_size=3
    )
    state = State(inputs={"prompt": "echo"}, results={}, structured_response=None)

    result = await node.run(state, {})

    assert result["response"].endswith(":: streamed")
    assert result["frames"]


@pytest.mark.asyncio
async def test_hallucination_guard_blocks_missing_markers() -> None:
    node = HallucinationGuardNode(name="guard")
    state = State(
        inputs={},
        results={
            "grounded_generator": {
                "response": "answer without markers",
                "citations": [{"id": "1", "snippet": "snippet"}],
            }
        },
        structured_response=None,
    )

    blocked = await node.run(state, {})

    assert blocked["allowed"] is False
    assert "missing citation markers" in blocked["reason"]


@pytest.mark.asyncio
async def test_hallucination_guard_allows_valid_output() -> None:
    node = HallucinationGuardNode(name="guard-allow")
    state = State(
        inputs={},
        results={
            "grounded_generator": {
                "response": "answer [1]",
                "citations": [{"id": "1", "snippet": "snippet"}],
            }
        },
        structured_response=None,
    )

    allowed = await node.run(state, {})

    assert allowed["allowed"] is True
    assert allowed["response"].startswith("answer")


@pytest.mark.asyncio
async def test_hallucination_guard_validates_payload_and_citations() -> None:
    node = HallucinationGuardNode(name="guard-extra")
    with pytest.raises(ValueError, match="mapping payload"):
        await node.run(
            State(
                inputs={}, results={"grounded_generator": []}, structured_response=None
            ),
            {},
        )

    state_missing = State(
        inputs={},
        results={"grounded_generator": {"response": "reply", "citations": []}},
        structured_response=None,
    )
    blocked = await node.run(state_missing, {})
    assert blocked["allowed"] is False

    state_bad = State(
        inputs={},
        results={
            "grounded_generator": {
                "response": "reply [1]",
                "citations": ["not-a-dict"],
            }
        },
        structured_response=None,
    )
    with pytest.raises(ValueError, match="Citations must be dictionaries"):
        await node.run(state_bad, {})


@pytest.mark.asyncio
async def test_hallucination_guard_blocks_empty_snippet() -> None:
    node = HallucinationGuardNode(name="guard-snippet")
    state = State(
        inputs={},
        results={
            "grounded_generator": {
                "response": "content [1]",
                "citations": [{"id": "1", "snippet": ""}],
            }
        },
        structured_response=None,
    )

    blocked = await node.run(state, {})
    assert blocked["allowed"] is False


@pytest.mark.asyncio
async def test_hallucination_guard_handles_empty_response_and_missing_ids() -> None:
    node = HallucinationGuardNode(name="guard-empty-response")
    empty_response_state = State(
        inputs={},
        results={"grounded_generator": {"response": "", "citations": []}},
        structured_response=None,
    )
    with pytest.raises(ValueError, match="Response payload is missing or empty"):
        await node.run(empty_response_state, {})

    node.require_markers = False
    allowed = await node.run(
        State(
            inputs={},
            results={
                "grounded_generator": {
                    "response": "text",
                    "citations": [{"snippet": "s"}],
                }
            },
            structured_response=None,
        ),
        {},
    )
    assert allowed["allowed"] is True

    missing_id_node = HallucinationGuardNode(name="guard-missing-id")
    allowed_missing = await missing_id_node.run(
        State(
            inputs={},
            results={
                "grounded_generator": {
                    "response": "ok",
                    "citations": [{"snippet": "s"}],
                }
            },
            structured_response=None,
        ),
        {},
    )
    assert allowed_missing["allowed"] is True


@pytest.mark.asyncio
async def test_reranker_and_router_prioritize_trusted_results() -> None:
    entries = [
        SearchResult(
            id="res-1",
            score=0.2,
            text="short text",
            metadata={"signal": "trusted"},
            source="vector",
        ),
        SearchResult(
            id="res-2",
            score=0.5,
            text="longer text passage",
            metadata={},
            source="bm25",
        ),
    ]

    def rerank(entry: SearchResult) -> float:
        bonus = 0.8 if entry.metadata.get("signal") == "trusted" else 0.0
        return entry.score + bonus

    reranker = ReRankerNode(
        name="rerank", rerank_function=rerank, length_penalty=0.0, top_k=2
    )
    state = State(
        inputs={},
        results={"retriever": {"results": entries}},
        structured_response=None,
    )

    reranked = await reranker.run(state, {})

    assert reranked["results"][0].id == "res-1"

    router = SourceRouterNode(name="router", min_score=0.3)
    routed = await router.run(state, {})

    assert set(routed["routed"].keys()) == {"vector", "bm25"}
    assert all(result.score >= 0.3 for result in routed["routed"]["bm25"])


@pytest.mark.asyncio
async def test_reranker_length_penalty_and_router_validation() -> None:
    entries = [
        SearchResult(
            id="alpha",
            score=0.6,
            text="lengthy text example",
            metadata={},
            source="hybrid",
        )
    ]
    reranker = ReRankerNode(name="rerank-penalty", length_penalty=0.1, top_k=1)
    reranked = await reranker.run(
        State(inputs={}, results={"retriever": entries}, structured_response=None), {}
    )

    assert reranked["results"][0].score < 0.6

    router = SourceRouterNode(name="router-invalid")
    with pytest.raises(ValueError, match="list of retrieval results"):
        await router.run(
            State(inputs={}, results={"retriever": "bad"}, structured_response=None),
            {},
        )

    with pytest.raises(ValueError, match="list of retrieval results"):
        await reranker.run(
            State(
                inputs={},
                results={"retriever": {"results": "oops"}},
                structured_response=None,
            ),
            {},
        )


@pytest.mark.asyncio
async def test_citations_formatter_normalizes_entries() -> None:
    citations = [
        {"id": "1", "snippet": "text", "sources": ["vector"]},
        {"id": "2", "snippet": "other", "sources": []},
    ]
    node = CitationsFormatterNode(name="formatter")
    state = State(
        inputs={},
        results={"grounded_generator": {"citations": citations}},
        structured_response=None,
    )

    formatted = await node.run(state, {})

    assert formatted["formatted"][0].startswith("[1]")
    assert formatted["citations"][0]["sources"] == ["vector"]


@pytest.mark.asyncio
async def test_citations_formatter_validates_payload() -> None:
    node = CitationsFormatterNode(name="formatter-invalid")
    with pytest.raises(ValueError, match="requires a list of citations"):
        await node.run(
            State(
                inputs={},
                results={"grounded_generator": "oops"},
                structured_response=None,
            ),
            {},
        )

    with pytest.raises(ValueError, match="Citation entries must be mappings"):
        await node.run(
            State(
                inputs={},
                results={"grounded_generator": {"citations": ["bad"]}},
                structured_response=None,
            ),
            {},
        )


@pytest.mark.asyncio
async def test_answer_caching_stores_and_serves_cached_response() -> None:
    node = AnswerCachingNode(name="cache", ttl_seconds=None, max_entries=2)

    first_state = State(
        inputs={"query": "What is Orcheo?"},
        results={"grounded_generator": {"response": "An orchestration engine."}},
        structured_response=None,
    )
    first = await node.run(first_state, {})
    assert first == {"cached": False, "response": "An orchestration engine."}

    second_state = State(
        inputs={"query": "What is Orcheo?"},
        results={},
        structured_response=None,
    )
    second = await node.run(second_state, {})

    assert second == {"cached": True, "response": "An orchestration engine."}


@pytest.mark.asyncio
async def test_answer_caching_handles_expiry_and_validation() -> None:
    node = AnswerCachingNode(name="cache-extra", ttl_seconds=1, max_entries=1)
    cache_state = State(
        inputs={"query": "Q1"},
        results={"grounded_generator": {"response": "first"}},
        structured_response=None,
    )
    await node.run(cache_state, {})
    node.cache["q1"] = ("first", time.time() - 1)

    expired = await node.run(
        State(inputs={"query": "Q1"}, results={}, structured_response=None), {}
    )
    assert expired["cached"] is False

    with pytest.raises(ValueError, match="non-empty query"):
        await node.run(
            State(inputs={"query": ""}, results={}, structured_response=None), {}
        )

    bad_response_state = State(
        inputs={"query": "Q2"},
        results={"grounded_generator": {"response": ""}},
        structured_response=None,
    )
    with pytest.raises(ValueError, match="non-empty string"):
        await node.run(bad_response_state, {})

    node._store("q3", "latest")
    node._store("q4", "newer")
    assert "q3" not in node.cache

    uncached = await node.run(
        State(
            inputs={"query": "Q5"},
            results={"grounded_generator": "skip"},
            structured_response=None,
        ),
        {},
    )
    assert uncached == {"cached": False, "response": None}


@pytest.mark.asyncio
async def test_session_management_prunes_history() -> None:
    store = InMemoryMemoryStore(max_total_turns=3)
    node = SessionManagementNode(name="session", memory_store=store, max_turns=2)
    state = State(
        inputs={
            "session_id": "sess-1",
            "turns": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {"role": "user", "content": "more"},
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["turn_count"] == 2
    assert [turn.content for turn in result["history"]] == ["hello", "more"]


@pytest.mark.asyncio
async def test_session_management_requires_session_id() -> None:
    node = SessionManagementNode(name="session-invalid")
    with pytest.raises(ValueError, match="requires a non-empty session id"):
        await node.run(State(inputs={}, results={}, structured_response=None), {})


@pytest.mark.asyncio
async def test_session_management_trims_session_id() -> None:
    node = SessionManagementNode(name="session-trim")
    state = State(
        inputs={"session_id": "  spaced  "},
        results={},
        structured_response=None,
    )
    result = await node.run(state, {})

    assert result["turn_count"] == 0


@pytest.mark.asyncio
async def test_multi_hop_planner_limits_hops() -> None:
    node = MultiHopPlannerNode(name="planner", max_hops=2)
    state = State(
        inputs={"query": "find revenue and summarize profit and share outlook"},
        results={},
        structured_response=None,
    )

    plan = await node.run(state, {})

    assert plan["hop_count"] == 2
    assert plan["plan"][0]["depends_on"] is None
    assert plan["plan"][1]["depends_on"] == plan["plan"][0]["id"]


@pytest.mark.asyncio
async def test_multi_hop_planner_handles_edge_cases() -> None:
    node = MultiHopPlannerNode(name="planner-edge")
    with pytest.raises(ValueError, match="requires a non-empty query"):
        await node.run(
            State(inputs={"query": ""}, results={}, structured_response=None), {}
        )

    fallback_plan = await node.run(
        State(inputs={"query": " and "}, results={}, structured_response=None), {}
    )
    assert fallback_plan["hop_count"] == 1


@pytest.mark.asyncio
async def test_streaming_generator_validates_prompt_and_llm_output() -> None:
    node = StreamingGeneratorNode(name="stream-invalid")
    with pytest.raises(ValueError, match="requires a non-empty prompt"):
        await node.run(
            State(inputs={"prompt": "   "}, results={}, structured_response=None), {}
        )

    bad_llm = StreamingGeneratorNode(name="stream-llm", llm=lambda *_: "")
    with pytest.raises(ValueError, match="LLM callable must return"):
        await bad_llm._invoke_llm("prompt")
