import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import telegramAgentConfig from "./assets/telegram-agent/config.json";
import telegramAgentScript from "./assets/telegram-agent/workflow.py?raw";

const TELEGRAM_AGENT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	root__start(["START"]):::first
	root__node__telegram_agent["telegram_agent"]
	subgraph root__telegram_agent__tool__send_telegram_message__subgraph["send_telegram_message"]
		root__telegram_agent__tool__send_telegram_message__start(["START"]):::toolBoundary
		root__telegram_agent__tool__send_telegram_message__node__send_telegram_message["send_telegram_message"]:::tool
		root__telegram_agent__tool__send_telegram_message__end(["END"]):::toolBoundary
		root__telegram_agent__tool__send_telegram_message__start --> root__telegram_agent__tool__send_telegram_message__node__send_telegram_message;
		root__telegram_agent__tool__send_telegram_message__node__send_telegram_message --> root__telegram_agent__tool__send_telegram_message__end;
	end
	root__node__telegram_agent -.-> root__telegram_agent__tool__send_telegram_message__start;
	root__end(["END"]):::last
	root__start --> root__node__telegram_agent;
	root__node__telegram_agent --> root__end;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
	classDef tool fill:#e8f6ef,stroke:#4d8f6a,line-height:1.2
	classDef toolBoundary fill:#f6faf8,stroke:#8ab79c,stroke-dasharray: 4 4
`;

export const TELEGRAM_AGENT_WORKFLOW: Workflow = {
  id: "template-telegram-agent",
  name: "Telegram Agent Sender",
  description:
    "Uses an agent with a MessageTelegram tool subworkflow, so the agent can decide whether to send to Telegram and what to send.",
  createdAt: "2026-03-10T12:00:00Z",
  updatedAt: "2026-03-10T12:00:00Z",
  sourceExample: "examples/agent_example.py",
  owner: TEMPLATE_OWNER,
  tags: ["template", "python", "agent", "telegram"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for workflow inputs and messages.",
      },
    },
    {
      id: "telegram_agent",
      type: "agent",
      position: { x: 280, y: 0 },
      data: {
        label: "AgentNode",
        type: "agent",
        description:
          "Decides whether Telegram should be used and, when needed, calls the embedded MessageTelegram tool workflow.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 560, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description:
          "Workflow completes after the agent replies or invokes Telegram.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-telegram-agent",
      source: "start",
      target: "telegram_agent",
    },
    {
      id: "edge-telegram-agent-end",
      source: "telegram_agent",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-telegram-agent-v1",
      mermaid: TELEGRAM_AGENT_MERMAID,
    },
  ],
};

export const TELEGRAM_AGENT_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: TELEGRAM_AGENT_WORKFLOW,
  script: telegramAgentScript,
  runnableConfig: telegramAgentConfig,
  notes: "Seeded from Telegram Agent Sender template.",
};
