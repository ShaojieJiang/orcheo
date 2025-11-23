"""Reference conversational search graph wiring ingestion to generation."""

from __future__ import annotations
from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.ingestion import (
    ChunkingStrategyNode,
    DocumentLoaderNode,
    EmbeddingIndexerNode,
)
from orcheo.nodes.conversational_search.retrieval import VectorSearchNode
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
)


def build_reference_conversational_search_graph(
    *, vector_store: BaseVectorStore | None = None
) -> StateGraph:
    """Return a reference ingestion → retrieval → generation graph."""
    store = vector_store or InMemoryVectorStore()

    graph = StateGraph(State)

    loader = DocumentLoaderNode(name="document_loader")
    chunker = ChunkingStrategyNode(name="chunking_strategy")
    indexer = EmbeddingIndexerNode(name="embedding_indexer", vector_store=store)
    retriever = VectorSearchNode(name="vector_search", vector_store=store)
    generator = GroundedGeneratorNode(
        name="grounded_generator", context_result_key="vector_search"
    )

    graph.add_node("document_loader", loader)
    graph.add_node("chunking_strategy", chunker)
    graph.add_node("embedding_indexer", indexer)
    graph.add_node("vector_search", retriever)
    graph.add_node("grounded_generator", generator)

    graph.add_edge(START, "document_loader")
    graph.add_edge("document_loader", "chunking_strategy")
    graph.add_edge("chunking_strategy", "embedding_indexer")
    graph.add_edge("embedding_indexer", "vector_search")
    graph.add_edge("vector_search", "grounded_generator")
    graph.add_edge("grounded_generator", END)

    graph.set_entry_point("document_loader")

    return graph
