import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search import (
    ChunkingStrategyNode,
    DocumentLoaderNode,
    EmbeddingIndexerNode,
    GroundedGeneratorNode,
    VectorSearchNode,
)
from orcheo.nodes.conversational_search.ingestion import RawDocumentInput
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_reference_pipeline_generates_grounded_answer() -> None:
    vector_store = InMemoryVectorStore()

    loader = DocumentLoaderNode(
        name="document_loader",
        documents=[
            RawDocumentInput(
                content="Orcheo delivers modular nodes for retrieval augmented generation.",
                metadata={"source": "primer"},
            ),
            RawDocumentInput(
                content="Grounded generation should always emit citations.",
                metadata={"source": "primer"},
            ),
        ],
    )
    chunker = ChunkingStrategyNode(
        name="chunking_strategy", chunk_size=64, chunk_overlap=8
    )
    indexer = EmbeddingIndexerNode(
        name="embedding_indexer", vector_store=vector_store, chunks_field="chunks"
    )
    retriever = VectorSearchNode(
        name="retriever",
        vector_store=vector_store,
        query_key="query",
        top_k=3,
    )
    generator = GroundedGeneratorNode(
        name="generator", context_result_key="retriever", context_field="results"
    )

    state = State(
        inputs={"query": "What does Orcheo deliver?"},
        results={},
        structured_response=None,
    )

    loader_result = await loader.run(state, {})
    state["results"][loader.name] = loader_result

    chunk_result = await chunker.run(state, {})
    state["results"][chunker.name] = chunk_result

    index_result = await indexer.run(state, {})
    state["results"][indexer.name] = index_result

    retrieval_result = await retriever.run(state, {})
    state["results"][retriever.name] = retrieval_result

    generation_result = await generator.run(state, {})

    assert generation_result["citations"]
    assert any(
        "Orcheo delivers" in citation["snippet"]
        for citation in generation_result["citations"]
    )
    assert "response" in generation_result
    assert "[1]" in generation_result["response"]
