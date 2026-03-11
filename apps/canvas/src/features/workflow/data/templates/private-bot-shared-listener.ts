import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import privateBotSharedListenerConfig from "./assets/private-bot-shared-listener/config.json";
import privateBotSharedListenerScript from "./assets/private-bot-shared-listener/workflow.py?raw";

const PRIVATE_BOT_SHARED_LISTENER_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	root__start(["START"]):::first
	root__node__telegram_listener["TelegramBotListenerNode"]
	root__node__discord_listener["DiscordBotListenerNode"]
	root__node__qq_listener["QQBotListenerNode"]
	root__node__agent_reply["AgentNode"]
	root__node__reply_route{"SwitchNode"}
	root__node__send_telegram["MessageTelegramNode"]
	root__node__send_discord["MessageDiscordNode"]
	root__node__send_qq["MessageQQNode"]
	root__end(["END"]):::last
	root__start --> root__node__telegram_listener;
	root__start --> root__node__discord_listener;
	root__start --> root__node__qq_listener;
	root__node__telegram_listener --> root__node__agent_reply;
	root__node__discord_listener --> root__node__agent_reply;
	root__node__qq_listener --> root__node__agent_reply;
	root__node__agent_reply --> root__node__reply_route;
	root__node__reply_route -->|telegram| root__node__send_telegram;
	root__node__reply_route -->|discord| root__node__send_discord;
	root__node__reply_route -->|qq| root__node__send_qq;
	root__node__send_telegram --> root__end;
	root__node__send_discord --> root__end;
	root__node__send_qq --> root__end;
	classDef default fill:#eef4ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#94b8ff
`;

export const PRIVATE_BOT_SHARED_LISTENER_WORKFLOW: Workflow = {
  id: "template-private-bot-shared-listener",
  name: "Private Bot Shared Listener",
  description:
    "Runs Telegram, Discord, and QQ listeners in parallel, reuses one AgentNode, and routes the reply through the matching platform node.",
  createdAt: "2026-03-11T12:00:00Z",
  updatedAt: "2026-03-11T12:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "telegram", "discord", "qq", "listener", "agent"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 120 },
      data: {
        label: "Start",
        type: "start",
        description: "Workflow entry point for listener-triggered runs.",
      },
    },
    {
      id: "telegram_listener",
      type: "trigger",
      position: { x: 230, y: 0 },
      data: {
        label: "TelegramBotListenerNode",
        type: "trigger",
        backendType: "TelegramBotListenerNode",
        description: "Receives Telegram listener events.",
      },
    },
    {
      id: "discord_listener",
      type: "trigger",
      position: { x: 230, y: 120 },
      data: {
        label: "DiscordBotListenerNode",
        type: "trigger",
        backendType: "DiscordBotListenerNode",
        description: "Receives Discord listener events.",
      },
    },
    {
      id: "qq_listener",
      type: "trigger",
      position: { x: 230, y: 240 },
      data: {
        label: "QQBotListenerNode",
        type: "trigger",
        backendType: "QQBotListenerNode",
        description: "Receives QQ listener events.",
      },
    },
    {
      id: "agent_reply",
      type: "agent",
      position: { x: 520, y: 120 },
      data: {
        label: "AgentNode",
        type: "agent",
        description: "Generates one shared reply for all listener platforms.",
      },
    },
    {
      id: "reply_route",
      type: "condition",
      position: { x: 790, y: 120 },
      data: {
        label: "SwitchNode",
        type: "condition",
        backendType: "SwitchNode",
        description: "Routes the shared reply to the matching platform node.",
        value: "{{inputs.platform}}",
        defaultBranchKey: "telegram",
        cases: [
          { match: "telegram", branchKey: "telegram", label: "Telegram" },
          { match: "discord", branchKey: "discord", label: "Discord" },
          { match: "qq", branchKey: "qq", label: "QQ" },
        ],
      },
    },
    {
      id: "send_telegram",
      type: "messaging",
      position: { x: 1070, y: 0 },
      data: {
        label: "MessageTelegramNode",
        type: "messaging",
        backendType: "MessageTelegramNode",
        description: "Sends the shared reply through Telegram.",
      },
    },
    {
      id: "send_discord",
      type: "messaging",
      position: { x: 1070, y: 120 },
      data: {
        label: "MessageDiscordNode",
        type: "messaging",
        backendType: "MessageDiscordNode",
        description: "Sends the shared reply through Discord.",
      },
    },
    {
      id: "send_qq",
      type: "messaging",
      position: { x: 1070, y: 240 },
      data: {
        label: "MessageQQNode",
        type: "messaging",
        backendType: "MessageQQNode",
        description: "Sends the shared reply through QQ.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 1340, y: 120 },
      data: {
        label: "Finish",
        type: "end",
        description: "The listener-triggered reply flow completes here.",
      },
    },
  ],
  edges: [
    { id: "edge-start-telegram", source: "start", target: "telegram_listener" },
    { id: "edge-start-discord", source: "start", target: "discord_listener" },
    { id: "edge-start-qq", source: "start", target: "qq_listener" },
    {
      id: "edge-telegram-agent",
      source: "telegram_listener",
      target: "agent_reply",
    },
    {
      id: "edge-discord-agent",
      source: "discord_listener",
      target: "agent_reply",
    },
    { id: "edge-qq-agent", source: "qq_listener", target: "agent_reply" },
    { id: "edge-agent-route", source: "agent_reply", target: "reply_route" },
    {
      id: "edge-route-telegram",
      source: "reply_route",
      target: "send_telegram",
      sourceHandle: "telegram",
    },
    {
      id: "edge-route-discord",
      source: "reply_route",
      target: "send_discord",
      sourceHandle: "discord",
    },
    {
      id: "edge-route-qq",
      source: "reply_route",
      target: "send_qq",
      sourceHandle: "qq",
    },
    { id: "edge-telegram-end", source: "send_telegram", target: "end" },
    { id: "edge-discord-end", source: "send_discord", target: "end" },
    { id: "edge-qq-end", source: "send_qq", target: "end" },
  ],
  versions: [
    {
      id: "template-private-bot-shared-listener-v1",
      mermaid: PRIVATE_BOT_SHARED_LISTENER_MERMAID,
    },
  ],
};

export const PRIVATE_BOT_SHARED_LISTENER_TEMPLATE: WorkflowTemplateDefinition =
  {
    workflow: PRIVATE_BOT_SHARED_LISTENER_WORKFLOW,
    script: privateBotSharedListenerScript,
    runnableConfig: privateBotSharedListenerConfig,
    notes: "Seeded from the shared private bot listener template.",
    metadata: {
      templateVersion: "1.0.0",
      minOrcheoVersion: "0.1.0",
      validatedProviderApi: "private-bot-listener-suite-2026-03-11",
      validationDate: "2026-03-11",
      owner: "Shaojie Jiang",
      acceptanceCriteria: [
        "Imports into Canvas without manual edits.",
        "Runs TelegramBotListenerNode, DiscordBotListenerNode, and QQBotListenerNode in one workflow.",
        "Routes one shared AgentNode reply through the matching platform send node only.",
      ],
      revalidationTriggers: [
        "Telegram, Discord, or QQ provider contract change",
        "MessageTelegramNode, MessageDiscordNode, or MessageQQNode contract change",
        "Listener runtime contract change",
      ],
      replyNodeContracts: [
        "MessageTelegramNode@1",
        "MessageDiscordNode@1",
        "MessageQQNode@1",
      ],
    },
  };
