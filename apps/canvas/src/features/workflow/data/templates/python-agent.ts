import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import agentScript from "./assets/python-agent/workflow.py?raw";

const AGENT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	ai_agent(ai_agent)
	__end__([<p>END</p>]):::last
	__start__ --> ai_agent;
	ai_agent --> __end__;
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
      id: "ai_agent",
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
      target: "ai_agent",
    },
    {
      id: "edge-agent-end",
      source: "ai_agent",
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
  script: agentScript,
  notes: "Seeded from Simple Agent template (`agent.py`).",
};
