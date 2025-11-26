from typing import Any
from langgraph.graph import StateGraph
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.ingestion import (
    ChunkingStrategyNode,
    DocumentLoaderNode,
    EmbeddingIndexerNode,
    MetadataExtractorNode,
)
from orcheo.nodes.conversational_search.retrieval import VectorSearchNode
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


# Default configuration inlined for server execution
DEFAULT_CONFIG = {
    "ingestion": {
        "chunking": {
            "chunk_size": 512,
            "chunk_overlap": 64,
        },
    },
    "retrieval": {
        "search": {
            "top_k": 5,
            "similarity_threshold": 0.0,
        },
    },
}


def create_ingestion_nodes(
    config: dict[str, Any], vector_store: InMemoryVectorStore
) -> dict[str, Any]:
    """Create and configure ingestion nodes."""
    loader = DocumentLoaderNode(name="loader")

    metadata = MetadataExtractorNode(
        name="metadata",
        source_result_key="loader",
    )

    chunking_config = config["ingestion"]["chunking"]
    chunking = ChunkingStrategyNode(
        name="chunking",
        source_result_key="metadata",
        chunk_size=chunking_config.get("chunk_size", 800),
        chunk_overlap=chunking_config.get("chunk_overlap", 80),
    )

    indexer = EmbeddingIndexerNode(
        name="indexer",
        source_result_key="chunking",
        vector_store=vector_store,
        # Using default deterministic embedding function
    )

    return {
        "loader": loader,
        "metadata": metadata,
        "chunking": chunking,
        "indexer": indexer,
    }


def create_search_nodes(
    config: dict[str, Any], vector_store: InMemoryVectorStore
) -> dict[str, Any]:
    """Create and configure search and generation nodes."""
    retrieval_config = config["retrieval"]["search"]
    search = VectorSearchNode(
        name="search",
        vector_store=vector_store,
        top_k=retrieval_config.get("top_k", 5),
        score_threshold=retrieval_config.get("similarity_threshold", 0.0),
    )

    # generation_config was unused, so we just instantiate the node
    generator = GroundedGeneratorNode(
        name="generator",
        context_result_key="search",
        # In a real app, we'd configure the LLM model here.
        # For this demo, we rely on the default mock/placeholder if available,
        # or we might need to mock the LLM call if GroundedGeneratorNode
        # requires a real one. GroundedGeneratorNode._default_llm is a placeholder.
    )

    return {"search": search, "generator": generator}


def define_workflow(ingestion_nodes: dict, search_nodes: dict) -> StateGraph:
    """Define the StateGraph workflow."""
    workflow = StateGraph(State)

    # Add nodes
    for name, node in ingestion_nodes.items():
        workflow.add_node(name, node)
    for name, node in search_nodes.items():
        workflow.add_node(name, node)

    # Define normalization node
    def normalize_input(state: dict) -> dict:
        inputs = state.get("inputs", {})
        # ChatKit sends "message", but VectorSearchNode expects "query"
        if "message" in inputs and "query" not in inputs:
            return {"inputs": {**inputs, "query": inputs["message"]}}
        return {}

    workflow.add_node("normalize", normalize_input)
    workflow.set_entry_point("normalize")

    # Define conditional routing from normalization
    def router(state: dict) -> str:
        inputs = state.get("inputs", {})
        # Prioritize ingestion if documents are present
        if "documents" in inputs:
            return "loader"
        elif "query" in inputs:
            return "search"
        else:
            raise ValueError("Invalid input state")

    def post_ingestion_router(state: dict) -> str:
        inputs = state.get("inputs", {})
        # After ingestion, check if we need to search
        if "query" in inputs:
            return "search"
        return "__end__"

    workflow.add_conditional_edges(
        "normalize",
        router,
        {
            "loader": "loader",
            "search": "search",
        },
    )

    # Ingestion flow
    workflow.add_edge("loader", "metadata")
    workflow.add_edge("metadata", "chunking")
    workflow.add_edge("chunking", "indexer")
    workflow.add_edge("chunking", "indexer")

    workflow.add_conditional_edges(
        "indexer",
        post_ingestion_router,
        {
            "search": "search",
            "__end__": "__end__",
        },
    )

    # Search flow
    workflow.add_edge("search", "generator")
    workflow.add_edge("generator", "__end__")

    return workflow


def build_graph():
    """Entrypoint for the Orcheo server to load the graph."""
    vector_store = InMemoryVectorStore()
    ingestion_nodes = create_ingestion_nodes(DEFAULT_CONFIG, vector_store)
    search_nodes = create_search_nodes(DEFAULT_CONFIG, vector_store)
    workflow = define_workflow(ingestion_nodes, search_nodes)
    return workflow


async def run_demo():
    """Run the demo workflow manually."""
    print("--- Starting Demo ---")
    app = build_graph().compile()

    print("\n--- Combined Ingestion and Search Phase ---")
    # Ingest a document and search immediately
    combined_input = {
        "inputs": {
            "documents": [
                {
                    "content": "Orcheo is a powerful workflow orchestration platform built on LangGraph. It allows users to create, manage, and execute complex workflows combining AI nodes, task nodes, and external integrations.",  # noqa: E501
                    "source": "manual_test",
                    "metadata": {"category": "tech"},
                }
            ],
            "message": "What is Orcheo?",
        }
    }
    # Use ainvoke for async execution
    result = await app.ainvoke(combined_input)
    print("Combined Results:", result.get("results", {}).keys())

    if "results" in result and "generator" in result["results"]:
        print("\nGenerator Output:", result["results"]["generator"])


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_demo())
