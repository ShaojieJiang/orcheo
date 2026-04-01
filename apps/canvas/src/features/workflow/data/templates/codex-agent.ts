import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import codexAgentConfig from "./assets/codex-agent/config.json";
import codexAgentScript from "./assets/codex-agent/workflow.py?raw";

const CODEX_AGENT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	codex_agent(codex_agent)
	__end__([<p>END</p>]):::last
	__start__ --> codex_agent;
	codex_agent --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const CODEX_AGENT_WORKFLOW: Workflow = {
  id: "template-codex-agent",
  name: "Codex Agent",
  description:
    "Runs Codex against the current repository using the flattened ChatKit conversation as the task prompt.",
  createdAt: "2026-04-01T09:00:00Z",
  updatedAt: "2026-04-01T09:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "codex", "agent", "external-agent"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for chat history and workflow inputs.",
      },
    },
    {
      id: "codex_agent",
      type: "agent",
      position: { x: 260, y: 0 },
      data: {
        label: "CodexNode",
        type: "agent",
        description:
          "Flattens the conversation into one prompt, runs Codex, and publishes the CLI output back into ChatKit.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 520, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Workflow completes after Codex returns its response.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-codex-agent",
      source: "start",
      target: "codex_agent",
    },
    {
      id: "edge-codex-agent-end",
      source: "codex_agent",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-codex-agent-v1",
      mermaid: CODEX_AGENT_MERMAID,
    },
  ],
};

export const CODEX_AGENT_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: CODEX_AGENT_WORKFLOW,
  script: codexAgentScript,
  runnableConfig: codexAgentConfig,
  notes: "Seeded from the Codex Agent template.",
};
