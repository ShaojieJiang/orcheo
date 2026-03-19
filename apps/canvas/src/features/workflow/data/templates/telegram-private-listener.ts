import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import telegramPrivateListenerConfig from "./assets/telegram-private-listener/config.json";
import telegramPrivateListenerScript from "./assets/telegram-private-listener/workflow.py?raw";

const TELEGRAM_PRIVATE_LISTENER_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	telegram_listener(telegram_listener)
	agent_reply(agent_reply)
	send_telegram(send_telegram)
	__end__([<p>END</p>]):::last
	__start__ --> telegram_listener;
	agent_reply --> send_telegram;
	telegram_listener --> agent_reply;
	send_telegram --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const TELEGRAM_PRIVATE_LISTENER_WORKFLOW: Workflow = {
  id: "template-telegram-private-listener",
  name: "Telegram Private Listener",
  description:
    "Receives Telegram bot messages over long polling, generates a reply with AgentNode, and sends it back through MessageTelegramNode.",
  createdAt: "2026-03-11T12:00:00Z",
  updatedAt: "2026-03-11T12:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "telegram", "listener", "agent"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Workflow entry point for listener-triggered runs.",
      },
    },
    {
      id: "telegram_listener",
      type: "trigger",
      position: { x: 250, y: 0 },
      data: {
        label: "TelegramBotListenerNode",
        type: "trigger",
        backendType: "TelegramBotListenerNode",
        description:
          "Normalizes Telegram listener events for downstream nodes.",
      },
    },
    {
      id: "agent_reply",
      type: "agent",
      position: { x: 520, y: 0 },
      data: {
        label: "AgentNode",
        type: "agent",
        description:
          "Generates the Telegram reply text from the listener event.",
      },
    },
    {
      id: "send_telegram",
      type: "messaging",
      position: { x: 800, y: 0 },
      data: {
        label: "MessageTelegramNode",
        type: "messaging",
        backendType: "MessageTelegramNode",
        description: "Sends the AgentNode reply back to the Telegram chat.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 1070, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "The listener-triggered reply flow completes here.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-listener",
      source: "start",
      target: "telegram_listener",
    },
    {
      id: "edge-listener-agent",
      source: "telegram_listener",
      target: "agent_reply",
    },
    {
      id: "edge-agent-send",
      source: "agent_reply",
      target: "send_telegram",
    },
    {
      id: "edge-send-end",
      source: "send_telegram",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-telegram-private-listener-v1",
      mermaid: TELEGRAM_PRIVATE_LISTENER_MERMAID,
    },
  ],
};

export const TELEGRAM_PRIVATE_LISTENER_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: TELEGRAM_PRIVATE_LISTENER_WORKFLOW,
  script: telegramPrivateListenerScript,
  runnableConfig: telegramPrivateListenerConfig,
  notes: "Seeded from Telegram Private Listener template.",
  metadata: {
    templateVersion: "1.0.0",
    minOrcheoVersion: "0.1.0",
    validatedProviderApi: "telegram-bot-api",
    validationDate: "2026-03-11",
    owner: "Shaojie Jiang",
    acceptanceCriteria: [
      "Imports into Canvas without manual edits.",
      "Runs TelegramBotListenerNode -> AgentNode -> MessageTelegramNode end to end.",
      "Documents required credentials and provider/API compatibility.",
    ],
    revalidationTriggers: [
      "Telegram Bot API major version change",
      "MessageTelegramNode contract change",
      "Listener runtime contract change",
    ],
    replyNodeContracts: ["MessageTelegramNode@1"],
  },
};
