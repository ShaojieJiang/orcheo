from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.edges import Condition, IfElse, Switch, SwitchCase
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.ingestion import (
    ChunkEmbeddingNode,
    ChunkingStrategyNode,
    DocumentLoaderNode,
    MetadataExtractorNode,
    VectorStoreUpsertNode,
)
from orcheo.nodes.conversational_search.retrieval import DenseSearchNode
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


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
    vector_store: InMemoryVectorStore,
) -> dict[str, Any]:
    """Create and configure ingestion nodes."""
    loader = DocumentLoaderNode(name="loader")

    metadata = MetadataExtractorNode(
        name="metadata",
        source_result_key="loader",
    )

    chunking = ChunkingStrategyNode(
        name="chunking",
        source_result_key="metadata",
        chunk_size="{{config.configurable.chunk_size}}",
        chunk_overlap="{{config.configurable.chunk_overlap}}",
    )

    chunk_embedding = ChunkEmbeddingNode(
        name="chunk_embedding",
        source_result_key="chunking",
        dense_embedding_specs={
            "default": {
                "embed_model": "openai:text-embedding-3-small",
                "model_kwargs": {"api_key": "[[openai_api_key]]"},
            }
        },
    )
    vector_upsert = VectorStoreUpsertNode(
        name="vector_upsert",
        source_result_key=chunk_embedding.name,
        vector_store=vector_store,
    )

    return {
        "loader": loader,
        "metadata": metadata,
        "chunking": chunking,
        "chunk_embedding": chunk_embedding,
        "vector_upsert": vector_upsert,
    }


def create_search_nodes(
    vector_store: InMemoryVectorStore,
) -> dict[str, Any]:
    """Create and configure search and generation nodes."""
    search = DenseSearchNode(
        name="search",
        vector_store=vector_store,
        top_k="{{config.configurable.top_k}}",
        score_threshold="{{config.configurable.similarity_threshold}}",
        embed_model="openai:text-embedding-3-small",
        model_kwargs={"api_key": "[[openai_api_key]]"},
    )

    # generation_config was unused, so we just instantiate the node
    generator = GroundedGeneratorNode(
        name="generator",
        context_result_key="search",
        ai_model="openai:gpt-4o-mini",
        model_kwargs={"api_key": "[[openai_api_key]]"},
        # The credential is retrieved from the orcheo credential vault
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
    workflow.add_edge("chunking", "chunk_embedding")
    workflow.add_edge("chunk_embedding", "vector_upsert")

    # Post-ingestion routing
    workflow.add_conditional_edges(
        "vector_upsert",
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


async def orcheo_workflow() -> StateGraph:
    """Entrypoint for the Orcheo server to load the graph."""
    vector_store = InMemoryVectorStore()
    ingestion_nodes = create_ingestion_nodes(vector_store)
    search_nodes = create_search_nodes(vector_store)
    routing_edges = create_routing_edges(vector_store)
    workflow = define_workflow(ingestion_nodes, search_nodes, routing_edges)
    return workflow
