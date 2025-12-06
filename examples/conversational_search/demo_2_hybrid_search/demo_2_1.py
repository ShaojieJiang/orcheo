"""Hybrid search Demo 2.1: construct the ingestion graph."""

from langgraph.graph import END, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.ingestion import (
    DEFAULT_EMBEDDING_METHOD_NAME,
    ChunkEmbeddingNode,
    ChunkingStrategyNode,
    DocumentLoaderNode,
    MetadataExtractorNode,
    RawDocumentInput,
    VectorStoreUpsertNode,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    PineconeVectorStore,
)


DEFAULT_DOCS_PATH = (
    "/Users/shaojiejiang/Development/orcheo/examples/conversational_search/data/docs"
)

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
DEFAULT_VECTOR_STORE_INDEX = "orcheo-demo"
DEFAULT_VECTOR_STORE_NAMESPACE = "hybrid_search"
DEFAULT_VECTOR_STORE_KWARGS = {"api_key": "[[pinecone_api_key]]"}


async def build_graph(
    vector_store: BaseVectorStore | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    embedding_method: str = DEFAULT_EMBEDDING_METHOD_NAME,
) -> StateGraph:
    """Construct the ingestion graph for the demo."""
    if vector_store is None:
        vector_store = PineconeVectorStore(
            index_name=DEFAULT_VECTOR_STORE_INDEX,
            namespace=DEFAULT_VECTOR_STORE_NAMESPACE,
            client_kwargs=DEFAULT_VECTOR_STORE_KWARGS,
        )
    document_loader = DocumentLoaderNode(
        name="document_loader",
        documents=[RawDocumentInput(storage_path=DEFAULT_DOCS_PATH)],
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
        embedding_methods={"default": embedding_method},
    )
    vector_upsert = VectorStoreUpsertNode(
        name="vector_upsert",
        source_result_key=chunk_embedder.name,
        vector_store=vector_store,
    )

    workflow = StateGraph(State)
    workflow.add_node("document_loader", document_loader)
    workflow.add_node("metadata_extractor", metadata_extractor)
    workflow.add_node("chunking_strategy", chunking)
    workflow.add_node("chunk_embedding", chunk_embedder)
    workflow.add_node("vector_upsert", vector_upsert)

    workflow.set_entry_point("document_loader")
    workflow.add_edge("document_loader", "metadata_extractor")
    workflow.add_edge("metadata_extractor", "chunking_strategy")
    workflow.add_edge("chunking_strategy", "chunk_embedding")
    workflow.add_edge("chunk_embedding", "vector_upsert")
    workflow.add_edge("vector_upsert", END)

    return workflow
