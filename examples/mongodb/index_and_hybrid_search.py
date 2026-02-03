"""MongoDB Atlas Search example workflow.

Configurable inputs (config.json):
- database: MongoDB database name
- collection: MongoDB collection name
- text_query: Full-text search query
- vector_path: Document field containing vector embeddings
"""

from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.mongodb import (
    MongoDBEnsureSearchIndexNode,
    MongoDBEnsureVectorIndexNode,
    MongoDBHybridSearchNode,
)


async def build_graph() -> StateGraph:
    """Build a workflow for index setup and hybrid search."""
    text_index = MongoDBEnsureSearchIndexNode(
        name="ensure_text_index",
        database="{{config.configurable.database}}",
        collection="{{config.configurable.collection}}",
        definition={
            "mappings": {
                "dynamic": False,
                "fields": {
                    "platform_name": {"type": "string"},
                    "recommendation_reason": {"type": "string"},
                },
            }
        },
        mode="ensure_or_update",
    )

    vector_index = MongoDBEnsureVectorIndexNode(
        name="ensure_vector_index",
        database="{{config.configurable.database}}",
        collection="{{config.configurable.collection}}",
        dimensions=3,
        similarity="cosine",
        path="{{config.configurable.vector_path}}",
        mode="ensure_or_update",
    )

    hybrid_search = MongoDBHybridSearchNode(
        name="hybrid_search",
        database="{{config.configurable.database}}",
        collection="{{config.configurable.collection}}",
        text_query="{{config.configurable.text_query}}",
        vector=[0.1, 0.2, 0.3],
        text_paths=["platform_name", "recommendation_reason"],
        vector_path="{{config.configurable.vector_path}}",
        top_k=5,
    )

    graph = StateGraph(State)
    graph.add_node("ensure_text_index", text_index)
    graph.add_node("ensure_vector_index", vector_index)
    graph.add_node("hybrid_search", hybrid_search)
    graph.add_edge(START, "ensure_text_index")
    graph.add_edge("ensure_text_index", "ensure_vector_index")
    graph.add_edge("ensure_vector_index", "hybrid_search")
    graph.add_edge("hybrid_search", END)

    return graph
