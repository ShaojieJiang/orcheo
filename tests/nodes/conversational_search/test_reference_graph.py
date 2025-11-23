import pytest
from langgraph.checkpoint.memory import InMemorySaver

from orcheo.nodes.conversational_search.reference_graph import (
    build_reference_conversational_search_graph,
)
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_reference_graph_runs_end_to_end() -> None:
    vector_store = InMemoryVectorStore()
    graph = build_reference_conversational_search_graph(vector_store=vector_store)

    checkpointer = InMemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "conv-search"}}

    documents = [
        {"content": "Orcheo ships conversational search nodes with citations."},
        {"content": "Vector and BM25 retrievers feed the grounded generator."},
    ]

    await compiled.ainvoke(
        {"inputs": {"documents": documents, "query": "What does Orcheo ship?"}},
        config,
    )

    state = compiled.get_state(config)
    results = state.values["results"]

    generated = results["grounded_generator"]

    assert generated["citations"]
    assert generated["tokens_used"] > 0
    assert "Orcheo" in generated["response"]
    assert "vector_search" in results
