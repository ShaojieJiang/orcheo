import asyncio
from pprint import pprint
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes import AgentNode, SetVariableNode


load_dotenv()


class DummyInputSchema(BaseModel):
    """Input for the tool workflow."""

    timestamp: int = Field(..., description="The timestamp to pass to the workflow.")


def tool_workflow() -> StateGraph:
    """Run the workflow and return the result."""
    graph = StateGraph(State)
    set_variable_node = SetVariableNode(
        name="set_variable",
        variables={"variable_name": "variable_value"},
    )
    graph.add_node("set_variable", set_variable_node)
    graph.add_edge(START, "set_variable")
    graph.add_edge("set_variable", END)
    return graph


def build_graph() -> StateGraph:
    """Build the graph."""
    graph = StateGraph(State)
    agent_node = AgentNode(
        name="agent",
        model_name="openai:gpt-4o-mini",
        workflow_tools=[
            {
                "name": "tool_workflow",
                "description": "Run the workflow and return the result.",
                "graph": tool_workflow(),
                "args_schema": DummyInputSchema,
            }
        ],
    )
    graph.add_node("agent", agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph


if __name__ == "__main__":
    workflow = build_graph().compile()
    result = asyncio.run(
        workflow.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Call the tool_workflow with timestamp 123!",
                    }
                ]
            }
        )
    )
    pprint(result)
