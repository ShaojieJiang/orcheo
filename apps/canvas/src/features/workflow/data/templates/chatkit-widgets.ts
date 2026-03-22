import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import chatkitWidgetsScript from "./assets/chatkit-widgets/workflow.py?raw";

const CHATKIT_WIDGETS_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	agent(agent)
	__end__([<p>END</p>]):::last
	__start__ --> agent;
	agent --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const CHATKIT_WIDGETS_WORKFLOW: Workflow = {
  id: "template-chatkit-widgets",
  name: "ChatKit Widgets Agent",
  description:
    "An agent that uses MCP ChatKit widget tools to render interactive UI components.",
  createdAt: "2026-03-21T09:00:00Z",
  updatedAt: "2026-03-21T09:00:00Z",
  sourceExample: "examples/chatkit_widgets/chatkit_widgets.py",
  owner: TEMPLATE_OWNER,
  tags: ["template", "python", "agent", "chatkit", "mcp", "widgets"],
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
      id: "agent",
      type: "agent",
      position: { x: 260, y: 0 },
      data: {
        label: "AgentNode",
        type: "agent",
        description:
          "Runs an AgentNode with MCP ChatKit widget tools for interactive UI.",
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
      target: "agent",
    },
    {
      id: "edge-agent-end",
      source: "agent",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-chatkit-widgets-v1",
      mermaid: CHATKIT_WIDGETS_MERMAID,
    },
  ],
};

export const CHATKIT_WIDGETS_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: CHATKIT_WIDGETS_WORKFLOW,
  script: chatkitWidgetsScript,
  notes: "Seeded from ChatKit Widgets template (`chatkit_widgets.py`).",
};
