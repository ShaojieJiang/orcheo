import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import claudeCodeAgentConfig from "./assets/claude-code-agent/config.json";
import claudeCodeAgentScript from "./assets/claude-code-agent/workflow.py?raw";

const CLAUDE_CODE_AGENT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	claude_code_agent(claude_code_agent)
	__end__([<p>END</p>]):::last
	__start__ --> claude_code_agent;
	claude_code_agent --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const CLAUDE_CODE_AGENT_WORKFLOW: Workflow = {
  id: "template-claude-code-agent",
  name: "Claude Code Agent",
  description:
    "Runs Claude Code against the current repository using the flattened ChatKit conversation as the task prompt.",
  createdAt: "2026-04-01T09:00:00Z",
  updatedAt: "2026-04-01T09:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "claude", "agent", "external-agent"],
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
      id: "claude_code_agent",
      type: "agent",
      position: { x: 260, y: 0 },
      data: {
        label: "ClaudeCodeNode",
        type: "agent",
        description:
          "Flattens the conversation into one prompt, runs Claude Code, and publishes the CLI output back into ChatKit.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 520, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description:
          "Workflow completes after Claude Code returns its response.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-claude-code-agent",
      source: "start",
      target: "claude_code_agent",
    },
    {
      id: "edge-claude-code-agent-end",
      source: "claude_code_agent",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-claude-code-agent-v1",
      mermaid: CLAUDE_CODE_AGENT_MERMAID,
    },
  ],
};

export const CLAUDE_CODE_AGENT_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: CLAUDE_CODE_AGENT_WORKFLOW,
  script: claudeCodeAgentScript,
  runnableConfig: claudeCodeAgentConfig,
  notes: "Seeded from the Claude Code Agent template.",
};
