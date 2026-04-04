import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import geminiAgentConfig from "./assets/gemini-agent/config.json";
import geminiAgentScript from "./assets/gemini-agent/workflow.py?raw";

const GEMINI_AGENT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	prepare_prompt(prepare_prompt)
	gemini_agent(gemini_agent)
	publish_reply(publish_reply)
	__end__([<p>END</p>]):::last
	__start__ --> prepare_prompt;
	gemini_agent --> publish_reply;
	prepare_prompt --> gemini_agent;
	publish_reply --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const GEMINI_AGENT_WORKFLOW: Workflow = {
  id: "template-gemini-agent",
  name: "Gemini Agent",
  description:
    "Runs Gemini CLI against the current repository using the flattened ChatKit conversation as the task prompt.",
  createdAt: "2026-04-04T15:00:00Z",
  updatedAt: "2026-04-04T15:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "gemini", "agent", "external-agent"],
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
      id: "gemini_agent",
      type: "agent",
      position: { x: 260, y: 0 },
      data: {
        label: "GeminiNode",
        type: "agent",
        description:
          "Flattens the conversation into one prompt, runs Gemini CLI, and publishes the CLI output back into ChatKit.",
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
          "Workflow completes after Gemini CLI returns its response.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-gemini-agent",
      source: "start",
      target: "gemini_agent",
    },
    {
      id: "edge-gemini-agent-end",
      source: "gemini_agent",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-gemini-agent-v1",
      mermaid: GEMINI_AGENT_MERMAID,
    },
  ],
};

export const GEMINI_AGENT_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: GEMINI_AGENT_WORKFLOW,
  script: geminiAgentScript,
  runnableConfig: geminiAgentConfig,
  notes: "Seeded from the Gemini Agent template.",
};
