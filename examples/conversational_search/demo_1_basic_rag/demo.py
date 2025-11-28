from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.edges import Condition, IfElse, Switch, SwitchCase
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
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


class EntryRoutingNode(TaskNode):
    """Determines the entry routing mode based on inputs and vector store state."""

    vector_store: InMemoryVectorStore = Field(
        description="Vector store to check for existing records"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compute routing decision."""
        inputs = state.get("inputs", {})
        has_docs = bool(inputs.get("documents"))

        if has_docs:
            routing_mode = "ingestion"
        elif self.vector_store.records:
            routing_mode = "search"
        else:
            routing_mode = "generator"

        return {"routing_mode": routing_mode}


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


def create_routing_edges(vector_store: InMemoryVectorStore) -> dict[str, Any]:
    """Create routing node and conditional edges for workflow routing."""
    # Entry routing node: computes routing decision and stores in state
    entry_routing_node = EntryRoutingNode(
        name="entry_routing",
        vector_store=vector_store,
    )

    # Entry router: Switch edge that reads routing decision from state
    entry_router = Switch(
        name="entry_router",
        value="{{entry_routing.routing_mode}}",  # Template string reads from state
        cases=[
            SwitchCase(match="ingestion", branch_key="loader"),
            SwitchCase(match="search", branch_key="search"),
            SwitchCase(match="generator", branch_key="generator"),
        ],
        default_branch_key="generator",
    )

    # Post-ingestion router: checks if query/message is present for search
    post_ingestion_router = IfElse(
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
        "entry_routing_node": entry_routing_node,
        "entry_router": entry_router,
        "post_ingestion_router": post_ingestion_router,
    }


def define_workflow(
    ingestion_nodes: dict, search_nodes: dict, routing_edges: dict
) -> StateGraph:
    """Define the StateGraph workflow."""
    workflow = StateGraph(State)

    # Add routing node
    entry_routing_node = routing_edges["entry_routing_node"]
    workflow.add_node("entry_routing", entry_routing_node)

    # Add task nodes
    for name, node in ingestion_nodes.items():
        workflow.add_node(name, node)
    for name, node in search_nodes.items():
        workflow.add_node(name, node)

    # Get routing edges
    entry_router = routing_edges["entry_router"]
    post_ingestion_router = routing_edges["post_ingestion_router"]

    # Set entry_routing as unconditional entry point
    workflow.set_entry_point("entry_routing")

    # Add conditional edges from entry_routing node
    workflow.add_conditional_edges(
        "entry_routing",
        entry_router,
        {
            "loader": "loader",
            "search": "search",
            "generator": "generator",
        },
    )

    # Ingestion flow
    workflow.add_edge("loader", "metadata")
    workflow.add_edge("metadata", "chunking")
    workflow.add_edge("chunking", "indexer")

    # Post-ingestion routing
    workflow.add_conditional_edges(
        "indexer",
        post_ingestion_router,
        {
            "true": "search",  # Query/message present -> search
            "false": END,  # No query/message -> end
        },
    )

    # Search flow
    workflow.add_edge("search", "generator")
    workflow.add_edge("generator", END)

    return workflow


def build_graph() -> StateGraph:
    """Entrypoint for the Orcheo server to load the graph."""
    vector_store = InMemoryVectorStore()
    ingestion_nodes = create_ingestion_nodes(DEFAULT_CONFIG, vector_store)
    search_nodes = create_search_nodes(DEFAULT_CONFIG, vector_store)
    routing_edges = create_routing_edges(vector_store)
    workflow = define_workflow(ingestion_nodes, search_nodes, routing_edges)
    return workflow


async def run_demo() -> None:
    """Run the demo workflow manually.

    This demo demonstrates both RAG and non-RAG modes:
    - RAG mode: Documents are provided and used for grounded generation
    - Non-RAG mode: No documents provided, generates general responses
    """
    import tempfile
    from pathlib import Path

    print("=== Starting Demo 1: Basic RAG Pipeline ===\n")

    # ========== NON-RAG MODE: Without Documents ==========
    # Test non-RAG mode first (before any documents are indexed)
    print("--- Non-RAG Mode: Direct Generation Phase ---")
    print("(Testing without any documents indexed)\n")

    app_non_rag = build_graph().compile()
    non_rag_input = {
        "inputs": {
            "message": "What is the capital of France?",
        }
    }

    result = await app_non_rag.ainvoke(non_rag_input)  # type: ignore[arg-type]
    print("Non-RAG Mode Results:", result.get("results", {}).keys())

    if "results" in result and "generator" in result["results"]:
        gen_result = result["results"]["generator"]
        print("\nNon-RAG Mode Generator Output:")
        print(f"  Reply: {gen_result.get('reply', 'N/A')[:100]}...")
        print(f"  Mode: {gen_result.get('mode', 'N/A')}")
        print(f"  Citations: {len(gen_result.get('citations', []))} found")

    # ========== RAG MODE: With Documents ==========
    print("\n--- RAG Mode: Ingestion and Search Phase ---")

    # Create a new app instance for RAG mode
    app_rag = build_graph().compile()

    # Phase 0: Simulate file upload (ChatKit behavior)
    # Create a temporary file to simulate uploaded document
    temp_dir = Path(tempfile.mkdtemp())
    doc_file = temp_dir / "atc_demo1234_document.txt"
    doc_content = "Orcheo is a powerful workflow orchestration platform built on LangGraph. It allows users to create, manage, and execute complex workflows combining AI nodes, task nodes, and external integrations."  # noqa: E501
    doc_file.write_text(doc_content, encoding="utf-8")

    # Phase 1: Workflow invocation with storage_path (not content)
    rag_input = {
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
        result = await app_rag.ainvoke(rag_input)  # type: ignore[arg-type]
        print("RAG Mode Results:", result.get("results", {}).keys())

        if "results" in result and "generator" in result["results"]:
            gen_result = result["results"]["generator"]
            print("\nRAG Mode Generator Output:")
            print(f"  Reply: {gen_result.get('reply', 'N/A')[:100]}...")
            print(f"  Mode: {gen_result.get('mode', 'N/A')}")
            print(f"  Citations: {len(gen_result.get('citations', []))} found")

    finally:
        # Cleanup temporary file
        doc_file.unlink()
        temp_dir.rmdir()

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_demo())
