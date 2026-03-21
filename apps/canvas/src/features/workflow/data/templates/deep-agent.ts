import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import deepAgentScript from "./assets/deep-agent/workflow.py?raw";

const DEEP_AGENT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	deep_agent(deep_agent)
	__end__([<p>END</p>]):::last
	__start__ --> deep_agent;
	deep_agent --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const DEEP_AGENT_WORKFLOW: Workflow = {
  id: "template-deep-agent",
  name: "Deep Research Agent",
  description:
    "An autonomous deep-research agent with multi-step tool use and synthesis.",
  createdAt: "2026-03-21T09:00:00Z",
  updatedAt: "2026-03-21T09:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "deep-agent", "research"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for research queries and workflow inputs.",
      },
    },
    {
      id: "deep_agent",
      type: "agent",
      position: { x: 260, y: 0 },
      data: {
        label: "DeepAgentNode",
        type: "agent",
        description:
          "Runs a deep research agent that plans, iterates over tools, and synthesises results.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 520, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Workflow completes after the agent returns its research.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-deep-agent",
      source: "start",
      target: "deep_agent",
    },
    {
      id: "edge-deep-agent-end",
      source: "deep_agent",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-deep-agent-v1",
      mermaid: DEEP_AGENT_MERMAID,
    },
  ],
};

export const DEEP_AGENT_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: DEEP_AGENT_WORKFLOW,
  script: deepAgentScript,
  notes: "Seeded from Deep Research Agent template (`deep-agent/workflow.py`).",
};
