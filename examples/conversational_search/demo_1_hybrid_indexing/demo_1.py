"""Build a hybrid indexing pipeline with dense and sparse embeddings for Pinecone.

Configurable inputs (config.json):
- urls: List of web page URLs to scrape and index
- chunk_size: Maximum characters per chunk
- chunk_overlap: Overlap between sequential chunks
- dense_embedding_method: Registered dense embedding method identifier
- sparse_embedding_method: Registered sparse embedding method identifier
- vector_store_index_dense: Pinecone index name for dense vectors
- vector_store_index_sparse: Pinecone index name for sparse vectors
- vector_store_namespace: Pinecone namespace for both stores
"""

from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.embedding_registry import (
    OPENAI_TEXT_EMBEDDING_3_SMALL,
    PINECONE_BM25_DEFAULT,
)
from orcheo.nodes.conversational_search.ingestion import (
    ChunkEmbeddingNode,
    ChunkingStrategyNode,
    MetadataExtractorNode,
    VectorStoreUpsertNode,
    WebDocumentLoaderNode,
)
from orcheo.nodes.conversational_search.vector_store import PineconeVectorStore


async def orcheo_workflow() -> StateGraph:
    """Build the hybrid indexing workflow."""
    dense_store = PineconeVectorStore(
        index_name="{{config.configurable.vector_store_index_dense}}",
        namespace="{{config.configurable.vector_store_namespace}}",
        client_kwargs={"api_key": "[[pinecone_api_key]]"},
    )
    sparse_store = PineconeVectorStore(
        index_name="{{config.configurable.vector_store_index_sparse}}",
        namespace="{{config.configurable.vector_store_namespace}}",
        client_kwargs={"api_key": "[[pinecone_api_key]]"},
    )

    document_loader = WebDocumentLoaderNode(
        name="document_loader",
        urls="{{config.configurable.urls}}",
        default_metadata={"demo": "hybrid_search"},
    )
    metadata_extractor = MetadataExtractorNode(
        name="metadata_extractor",
        infer_title_from_first_line=True,
    )
    chunking = ChunkingStrategyNode(
        name="chunking_strategy",
        source_result_key=metadata_extractor.name,
        chunk_size=512,
        chunk_overlap=64,
    )
    chunk_embedder = ChunkEmbeddingNode(
        name="chunk_embedding",
        source_result_key=chunking.name,
        embedding_methods={
            "dense": OPENAI_TEXT_EMBEDDING_3_SMALL,
            "bm25": PINECONE_BM25_DEFAULT,
        },
        credential_env_vars={"OPENAI_API_KEY": "[[openai_api_key]]"},
    )
    dense_vector_upsert = VectorStoreUpsertNode(
        name="vector_upsert_dense",
        source_result_key=chunk_embedder.name,
        embedding_names=["dense"],
        vector_store=dense_store,
    )
    sparse_vector_upsert = VectorStoreUpsertNode(
        name="vector_upsert_sparse",
        source_result_key=chunk_embedder.name,
        embedding_names=["bm25"],
        vector_store=sparse_store,
    )

    workflow = StateGraph(State)
    workflow.add_node("document_loader", document_loader)
    workflow.add_node("metadata_extractor", metadata_extractor)
    workflow.add_node("chunking_strategy", chunking)
    workflow.add_node("chunk_embedding", chunk_embedder)
    workflow.add_node("vector_upsert_dense", dense_vector_upsert)
    workflow.add_node("vector_upsert_sparse", sparse_vector_upsert)
    workflow.add_edge(START, "document_loader")
    workflow.add_edge("document_loader", "metadata_extractor")
    workflow.add_edge("metadata_extractor", "chunking_strategy")
    workflow.add_edge("chunking_strategy", "chunk_embedding")
    workflow.add_edge("chunk_embedding", "vector_upsert_dense")
    workflow.add_edge("vector_upsert_dense", "vector_upsert_sparse")
    workflow.add_edge("vector_upsert_sparse", END)

    return workflow
