import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.ingestion import (
    ChunkingStrategyNode,
    DocumentLoaderNode,
    EmbeddingIndexerNode,
)
from orcheo.nodes.conversational_search.retrieval import VectorSearchNode
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_ingestion_to_generation_pipeline_produces_grounded_response() -> None:
    vector_store = InMemoryVectorStore()
    document_loader = DocumentLoaderNode(name="document_loader")
    chunker = ChunkingStrategyNode(name="chunking_strategy", chunk_size=64)
    indexer = EmbeddingIndexerNode(
        name="embedding_indexer", vector_store=vector_store, chunk_overlap=0
    )
    retriever = VectorSearchNode(
        name="vector_retrieval", vector_store=vector_store, top_k=1
    )
    generator = GroundedGeneratorNode(
        name="grounded_generator", context_result_key="vector_retrieval"
    )

    state = State(
        inputs={
            "documents": [
                {
                    "content": "Orcheo builds composable graph workflows for AI systems.",
                    "metadata": {"page": 1},
                }
            ],
            "query": "What does Orcheo build?",
        },
        results={},
        structured_response=None,
    )

    state["results"][document_loader.name] = await document_loader.run(state, {})
    state["results"][chunker.name] = await chunker.run(state, {})
    state["results"][indexer.name] = await indexer.run(state, {})
    state["results"][retriever.name] = await retriever.run(state, {})

    generation = await generator.run(state, {})

    assert "Orcheo builds" in generation["response"]
    assert generation["citations"][0]["source_id"].endswith("chunk-0")
    assert generation["attempts"] == 1
    assert generation["tokens_used"] > 5
