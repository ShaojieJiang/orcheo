import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search import (
    ConversationCompressorNode,
    ConversationStateNode,
    ChunkingStrategyNode,
    DocumentLoaderNode,
    EmbeddingIndexerNode,
    GroundedGeneratorNode,
    MemorySummarizerNode,
    QueryClarificationNode,
    TopicShiftDetectorNode,
    VectorSearchNode,
)
from orcheo.nodes.conversational_search.ingestion import RawDocumentInput
from orcheo.nodes.conversational_search.conversation import InMemoryMemoryStore
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


@pytest.mark.asyncio
async def test_reference_pipeline_supports_multi_turn_with_compression_and_routing() -> (
    None
):
    vector_store = InMemoryVectorStore()

    memory_store = InMemoryMemoryStore()
    conversation_state = ConversationStateNode(
        name="conversation_state", memory_store=memory_store, max_turns=5
    )
    conversation_compressor = ConversationCompressorNode(
        name="conversation_compressor", max_tokens=5, summary_max_tokens=6
    )
    topic_detector = TopicShiftDetectorNode(
        name="topic_detector", min_overlap_ratio=0.4
    )
    clarifier = QueryClarificationNode(name="clarifier")
    memory_summarizer = MemorySummarizerNode(
        name="memory_summarizer", memory_store=memory_store, retention_summaries=2
    )

    loader = DocumentLoaderNode(
        name="document_loader",
        documents=[
            RawDocumentInput(
                content="Orcheo uses hybrid retrieval across vector and BM25 indices.",
                metadata={"source": "primer"},
            ),
            RawDocumentInput(
                content="Topic shifts can route users to fresh retrieval flows.",
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
        top_k=2,
    )
    generator = GroundedGeneratorNode(
        name="generator", context_result_key="retriever", context_field="results"
    )

    state = State(
        inputs={
            "query": "How does retrieval work?",
            "session_id": "sess",
            "user_message": "How does retrieval work?",
        },
        results={},
        structured_response=None,
    )

    loader_result = await loader.run(state, {})
    state["results"][loader.name] = loader_result
    chunk_result = await chunker.run(state, {})
    state["results"][chunker.name] = chunk_result
    index_result = await indexer.run(state, {})
    state["results"][indexer.name] = index_result

    convo_result = await conversation_state.run(state, {})
    state["results"][conversation_state.name] = convo_result
    compressor_result = await conversation_compressor.run(state, {})
    state["results"][conversation_compressor.name] = compressor_result
    topic_result = await topic_detector.run(state, {})
    state["results"][topic_detector.name] = topic_result
    clarifier_result = await clarifier.run(state, {})
    state["results"][clarifier.name] = clarifier_result

    retrieval_result = await retriever.run(state, {})
    state["results"][retriever.name] = retrieval_result
    generation_result = await generator.run(state, {})

    assert compressor_result["summary"] is None
    assert topic_result["topic_shift"] is False
    assert clarifier_result["needs_clarification"] is False
    assert generation_result["citations"]

    # New topic turn triggers topic shift and clarification prompt
    state["inputs"]["query"] = "Switching to pricing details"
    state["inputs"]["user_message"] = "Switching to pricing details"

    convo_result = await conversation_state.run(state, {})
    state["results"][conversation_state.name] = convo_result
    compressor_result = await conversation_compressor.run(state, {})
    state["results"][conversation_compressor.name] = compressor_result
    topic_result = await topic_detector.run(state, {})
    state["results"][topic_detector.name] = topic_result
    clarifier_result = await clarifier.run(state, {})

    assert compressor_result["summary"] is not None
    assert topic_result["topic_shift"] is True
    assert clarifier_result["needs_clarification"] is True

    summary_result = await memory_summarizer.run(state, {})

    assert summary_result["summary_count"] >= 1
