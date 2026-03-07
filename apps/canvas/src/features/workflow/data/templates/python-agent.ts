import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";

const AGENT_SCRIPT = `from langgraph.graph import StateGraph
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode

def orcheo_workflow() -> StateGraph:
    graph = StateGraph(State)
    agent = AgentNode(
        name="assistant_agent",
        ai_model="openai:gpt-4o-mini",
        system_prompt="You are a helpful assistant for workflow demos.",
        model_kwargs={"api_key": "[[openai_api_key]]"},
    )
    graph.add_node("assistant_agent", agent)
    graph.set_entry_point("assistant_agent")
    graph.set_finish_point("assistant_agent")
    return graph
`;

const AGENT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	assistant_agent(assistant_agent)
	__end__([<p>__end__</p>]):::last
	__start__ --> assistant_agent;
	assistant_agent --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const PYTHON_AGENT_WORKFLOW: Workflow = {
  id: "template-python-agent",
  name: "Simple Agent",
  description: "A single-node agent workflow seeded from `agent.py`.",
  createdAt: "2026-03-01T09:00:00Z",
  updatedAt: "2026-03-01T09:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "python", "agent"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for messages and workflow inputs.",
      },
    },
    {
      id: "assistant_agent",
      type: "agent",
      position: { x: 260, y: 0 },
      data: {
        label: "AgentNode",
        type: "agent",
        description: "Runs one AgentNode with a system prompt and AI model.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 520, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Workflow completes after the agent response.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-agent",
      source: "start",
      target: "assistant_agent",
    },
    {
      id: "edge-agent-end",
      source: "assistant_agent",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-python-agent-v1",
      mermaid: AGENT_MERMAID,
    },
  ],
};

export const PYTHON_AGENT_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: PYTHON_AGENT_WORKFLOW,
  script: AGENT_SCRIPT,
  notes: "Seeded from Simple Agent template (`agent.py`).",
};
