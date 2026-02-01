"""Build a hybrid indexing pipeline with dense and sparse embeddings for Pinecone."""

from langgraph.graph import END, StateGraph
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
    WebDocumentInput,
    WebDocumentLoaderNode,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    PineconeVectorStore,
)


DEFAULT_DOC_URLS = [
    "https://raw.githubusercontent.com/ShaojieJiang/orcheo/refs/heads/main/docs/index.md",
    "https://raw.githubusercontent.com/ShaojieJiang/orcheo/refs/heads/main/docs/manual_setup.md",
]

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
DEFAULT_VECTOR_STORE_INDEX_DENSE = "orcheo-demo-dense"
DEFAULT_VECTOR_STORE_INDEX_SPARSE = "orcheo-demo-sparse"
DEFAULT_VECTOR_STORE_NAMESPACE = "hybrid_search"
DEFAULT_VECTOR_STORE_KWARGS = {"api_key": "[[pinecone_api_key]]"}


async def build_graph(
    dense_embedding_method: str = OPENAI_TEXT_EMBEDDING_3_SMALL,
    sparse_embedding_method: str = PINECONE_BM25_DEFAULT,
    vector_store: BaseVectorStore | None = None,
    dense_vector_store: BaseVectorStore | None = None,
    sparse_vector_store: BaseVectorStore | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> StateGraph:
    """Construct the ingestion graph for the demo."""
    dense_store = dense_vector_store or vector_store
    sparse_store = sparse_vector_store or vector_store
    if dense_store is None:
        dense_store = PineconeVectorStore(
            index_name=DEFAULT_VECTOR_STORE_INDEX_DENSE,
            namespace=DEFAULT_VECTOR_STORE_NAMESPACE,
            client_kwargs=DEFAULT_VECTOR_STORE_KWARGS,
        )
    if sparse_store is None:
        sparse_store = PineconeVectorStore(
            index_name=DEFAULT_VECTOR_STORE_INDEX_SPARSE,
            namespace=DEFAULT_VECTOR_STORE_NAMESPACE,
            client_kwargs=DEFAULT_VECTOR_STORE_KWARGS,
        )
    document_loader = WebDocumentLoaderNode(
        name="document_loader",
        urls=[WebDocumentInput(url=url) for url in DEFAULT_DOC_URLS],
        default_metadata={"demo": "hybrid_search"},
    )
    metadata_extractor = MetadataExtractorNode(
        name="metadata_extractor",
        infer_title_from_first_line=True,
    )
    chunking = ChunkingStrategyNode(
        name="chunking_strategy",
        source_result_key=metadata_extractor.name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunk_embedder = ChunkEmbeddingNode(
        name="chunk_embedding",
        source_result_key=chunking.name,
        embedding_methods={
            "dense": dense_embedding_method,
            "bm25": sparse_embedding_method,
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

    workflow.set_entry_point("document_loader")
    workflow.add_edge("document_loader", "metadata_extractor")
    workflow.add_edge("metadata_extractor", "chunking_strategy")
    workflow.add_edge("chunking_strategy", "chunk_embedding")
    workflow.add_edge("chunk_embedding", "vector_upsert_dense")
    workflow.add_edge("vector_upsert_dense", "vector_upsert_sparse")
    workflow.add_edge("vector_upsert_sparse", END)

    return workflow
