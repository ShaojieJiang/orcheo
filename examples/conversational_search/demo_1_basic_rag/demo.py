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
from orcheo.nodes.logic.branching import IfElseNode
from orcheo.nodes.logic.conditions import Condition


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


def create_routing_nodes() -> dict[str, Any]:
    """Create branching nodes for workflow routing."""
    # Entry router: checks if documents are present
    entry_router = IfElseNode(
        name="entry_router",
        conditions=[
            Condition(
                left="{{inputs.documents}}",
                operator="is_truthy",
            )
        ],
    )

    # Post-ingestion router: checks if query/message is present for search
    post_ingestion_router = IfElseNode(
        name="post_ingestion_router",
        conditions=[
            Condition(
                left="{{inputs.message}}",
                operator="is_truthy",
            ),
            Condition(
                left="{{inputs.message}}",
                operator="is_truthy",
            ),
        ],
        condition_logic="or",
    )

    return {
        "entry_router": entry_router,
        "post_ingestion_router": post_ingestion_router,
    }


def define_workflow(
    ingestion_nodes: dict, search_nodes: dict, routing_nodes: dict
) -> StateGraph:
    """Define the StateGraph workflow."""
    workflow = StateGraph(State)

    # Add task nodes only (DecisionNodes are used directly in conditional edges)
    for name, node in ingestion_nodes.items():
        workflow.add_node(name, node)
    for name, node in search_nodes.items():
        workflow.add_node(name, node)

    # Entry router as conditional entry point (DecisionNode used directly)
    entry_router = routing_nodes["entry_router"]
    workflow.set_conditional_entry_point(
        entry_router,
        {
            "true": "loader",  # Documents present -> ingestion
            "false": "search",  # No documents -> search
        },
    )

    # Ingestion flow
    workflow.add_edge("loader", "metadata")
    workflow.add_edge("metadata", "chunking")
    workflow.add_edge("chunking", "indexer")

    # Post-ingestion routing (DecisionNode used directly)
    post_ingestion_router = routing_nodes["post_ingestion_router"]
    workflow.add_conditional_edges(
        "indexer",
        post_ingestion_router,
        {
            "true": "search",  # Query/message present -> search
            "false": "__end__",  # No query/message -> end
        },
    )

    # Search flow
    workflow.add_edge("search", "generator")
    workflow.add_edge("generator", "__end__")

    return workflow


def build_graph() -> StateGraph:
    """Entrypoint for the Orcheo server to load the graph."""
    vector_store = InMemoryVectorStore()
    ingestion_nodes = create_ingestion_nodes(DEFAULT_CONFIG, vector_store)
    search_nodes = create_search_nodes(DEFAULT_CONFIG, vector_store)
    routing_nodes = create_routing_nodes()
    workflow = define_workflow(ingestion_nodes, search_nodes, routing_nodes)
    return workflow


async def run_demo() -> None:
    """Run the demo workflow manually.

    This demo aligns with the ChatKit dataflow where files are stored on disk
    and only storage_path (not content) is passed to the workflow. The
    DocumentLoaderNode reads file content from storage_path during execution.
    """
    import tempfile
    from pathlib import Path

    print("--- Starting Demo ---")
    app = build_graph().compile()

    print("\n--- Combined Ingestion and Search Phase ---")

    # Phase 0: Simulate file upload (ChatKit behavior)
    # Create a temporary file to simulate uploaded document
    temp_dir = Path(tempfile.mkdtemp())
    doc_file = temp_dir / "atc_demo1234_document.txt"
    doc_content = "Orcheo is a powerful workflow orchestration platform built on LangGraph. It allows users to create, manage, and execute complex workflows combining AI nodes, task nodes, and external integrations."  # noqa: E501
    doc_file.write_text(doc_content, encoding="utf-8")

    # Phase 1: Workflow invocation with storage_path (not content)
    # Aligns with dataflow.md Phase 1 where content is NOT included
    combined_input = {
        "inputs": {
            "documents": [
                {
                    "storage_path": str(doc_file),  # Path to file on disk
                    "source": "document.txt",
                    "metadata": {"category": "tech"},
                }
            ],
            "message": "What is Orcheo?",
        }
    }

    try:
        # Use ainvoke for async execution
        result = await app.ainvoke(combined_input)  # type: ignore[arg-type]
        print("Combined Results:", result.get("results", {}).keys())

        if "results" in result and "generator" in result["results"]:
            print("\nGenerator Output:", result["results"]["generator"])
    finally:
        # Cleanup temporary file
        doc_file.unlink()
        temp_dir.rmdir()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_demo())
