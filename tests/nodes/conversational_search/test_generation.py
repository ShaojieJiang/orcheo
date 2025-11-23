import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search import (
    ChunkingStrategyNode,
    DocumentLoaderNode,
    EmbeddingIndexerNode,
    GroundedGeneratorNode,
    VectorSearchNode,
)
from orcheo.nodes.conversational_search.ingestion import (
    deterministic_embedding_function,
)
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_grounded_generator_emits_citations() -> None:
    context = [
        SearchResult(
            id="chunk-1",
            score=0.9,
            text="Orcheo enables graph-native workflows.",
            metadata={"source": "doc"},
            source="vector",
            sources=["vector"],
        ),
        SearchResult(
            id="chunk-2",
            score=0.8,
            text="It provides conversational search primitives.",
            metadata={"source": "doc"},
            source="vector",
            sources=["vector"],
        ),
    ]
    node = GroundedGeneratorNode(name="generator")
    state = State(
        inputs={"query": "What is Orcheo?"},
        results={"retrieval_results": {"results": context}},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["citations"][0]["source_id"] == "chunk-1"
    assert len(result["citations"]) == 2
    assert "[1]" in result["response"]
    assert result["tokens_used"] > 0


@pytest.mark.asyncio
async def test_grounded_generator_retries_on_failure() -> None:
    attempts = 0

    async def flaky_generator(query: str, context: list[SearchResult]) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            msg = "transient"
            raise RuntimeError(msg)
        return f"Final answer with {len(context)} sources [1]"

    context = [
        SearchResult(
            id="chunk-1",
            score=0.9,
            text="retries are supported",
            metadata={},
            source="vector",
            sources=["vector"],
        )
    ]
    node = GroundedGeneratorNode(
        name="generator-retry",
        generator=flaky_generator,
        max_retries=2,
        backoff_seconds=0.0,
    )
    state = State(
        inputs={"query": "test retries"},
        results={"retrieval_results": {"results": context}},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert attempts == 2
    assert result["response"].startswith("Final answer")


@pytest.mark.asyncio
async def test_end_to_end_pipeline_generates_grounded_answer() -> None:
    vector_store = InMemoryVectorStore()
    loader = DocumentLoaderNode(name="document_loader")
    chunker = ChunkingStrategyNode(
        name="chunking_strategy", chunk_size=64, chunk_overlap=0
    )
    indexer = EmbeddingIndexerNode(
        name="embedding_indexer",
        vector_store=vector_store,
        embedding_function=deterministic_embedding_function,
    )
    retriever = VectorSearchNode(
        name="vector_search",
        vector_store=vector_store,
        top_k=2,
        embedding_function=deterministic_embedding_function,
    )
    generator = GroundedGeneratorNode(name="grounded_generator")

    query = "What capabilities does Orcheo provide?"
    seed_state = State(
        inputs={
            "documents": [
                "Orcheo enables graph-native workflows and conversational search.",
                "It also includes ingestion, retrieval, and generation primitives.",
            ],
            "query": query,
        },
        results={},
        structured_response=None,
    )

    documents = await loader.run(seed_state, {})
    chunks = await chunker.run(
        State(
            inputs={}, results={"document_loader": documents}, structured_response=None
        ),
        {},
    )
    await indexer.run(
        State(
            inputs={}, results={"chunking_strategy": chunks}, structured_response=None
        ),
        {},
    )

    retrieval = await retriever.run(
        State(inputs={"query": query}, results={}, structured_response=None),
        {},
    )
    generation = await generator.run(
        State(
            inputs={"query": query},
            results={"retrieval_results": retrieval},
            structured_response=None,
        ),
        {},
    )

    assert generation["citations"]
    assert len(generation["citations"]) == len(retrieval["results"])
    assert "[1]" in generation["response"]
    assert generation["tokens_used"] >= len(query.split())
