"""MongoDB node example."""

import asyncio
import time
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.mongodb import MongoDBNode


async def main():
    """Main function to demonstrate persistent MongoDB session."""
    load_dotenv()

    # Create the MongoDB node (session will be created on first use)
    mongodb_node = MongoDBNode(
        name="mongodb_node",
        database="Orcheo",
        collection="rss_feeds",
        operation="find",
        query={"read": False},
    )

    # Build the graph
    graph = StateGraph(State)
    graph.add_node("mongodb_node", mongodb_node)
    graph.add_edge(START, "mongodb_node")
    graph.add_edge("mongodb_node", END)
    compiled_graph = graph.compile()

    # First execution - will create the session
    print("First execution (creates session):")
    start_time = time.time()
    result = await compiled_graph.ainvoke({})
    end_time = time.time()
    print(f"Execution time: {end_time - start_time:.2f}s")
    print(result)
    print()

    # Second execution - reuses the same session
    print("Second execution (reuses session):")
    start_time = time.time()
    result = await compiled_graph.ainvoke({})
    end_time = time.time()
    print(f"Execution time: {end_time - start_time:.2f}s")
    print(result)
    print()

    # Third execution - still reusing the session
    print("Third execution (still reusing session):")
    start_time = time.time()
    result = await compiled_graph.ainvoke({})
    end_time = time.time()
    print(f"Execution time: {end_time - start_time:.2f}s")
    print(result)

    print("\nSession will automatically close when process exits.")


if __name__ == "__main__":
    asyncio.run(main())
