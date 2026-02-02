"""MongoDB Atlas Search example."""

import asyncio
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.mongodb import (
    MongoDBEnsureSearchIndexNode,
    MongoDBEnsureVectorIndexNode,
    MongoDBHybridSearchNode,
)


async def main() -> None:
    """Build a simple workflow for index setup + hybrid search."""
    load_dotenv()

    text_index = MongoDBEnsureSearchIndexNode(
        name="ensure_text_index",
        database="Orcheo",
        collection="documents",
        definition={
            "mappings": {
                "dynamic": False,
                "fields": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
            }
        },
        mode="ensure_or_update",
    )

    vector_index = MongoDBEnsureVectorIndexNode(
        name="ensure_vector_index",
        database="Orcheo",
        collection="documents",
        dimensions=3,
        similarity="cosine",
        path="embedding",
        mode="ensure_or_update",
    )

    hybrid_search = MongoDBHybridSearchNode(
        name="hybrid_search",
        database="Orcheo",
        collection="documents",
        text_query="orcheo",
        vector=[0.1, 0.2, 0.3],
        text_paths=["title", "body"],
        vector_path="embedding",
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

    compiled_graph = graph.compile()
    result = await compiled_graph.ainvoke({})
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
