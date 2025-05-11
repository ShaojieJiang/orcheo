"""Example graph demonstrating state handling."""

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from aic_flow.graph.state import State
from aic_flow.nodes.base import TaskNode


class Node1(TaskNode):
    """Node 1."""

    def run(self, state: State, config: RunnableConfig) -> dict:
        """Run the node."""
        return {"a": 1}


class Node2(TaskNode):
    """Node 2."""

    def run(self, state: State, config: RunnableConfig) -> dict:
        """Run the node."""
        return "b"


class Node3(TaskNode):
    """Node 3."""

    def run(self, state: State, config: RunnableConfig) -> dict:
        """Run the node."""
        return ["c"]


def main() -> None:
    """Main function."""
    graph = StateGraph(State)
    graph.add_node("node1", Node1("node1"))
    graph.add_node("node2", Node2("node2"))
    graph.add_node("node3", Node3("node3"))

    graph.add_edge(START, "node1")
    graph.add_edge("node1", "node2")
    graph.add_edge("node2", "node3")
    graph.add_edge("node3", END)

    checkpointer = InMemorySaver()
    compiled_graph = graph.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": 1}}
    compiled_graph.invoke({}, config)
    state = compiled_graph.get_state(config)
    print(state.values)
    # {'messages': [], 'outputs': {'node1': {'a': 1}, 'node2': 'b', 'node3': ['c']}}


if __name__ == "__main__":
    main()
