import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import discordPrivateListenerConfig from "./assets/discord-private-listener/config.json";
import discordPrivateListenerScript from "./assets/discord-private-listener/workflow.py?raw";

const DISCORD_PRIVATE_LISTENER_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	discord_listener(discord_listener)
	agent_reply(agent_reply)
	send_discord(send_discord)
	__end__([<p>END</p>]):::last
	__start__ --> discord_listener;
	agent_reply --> send_discord;
	discord_listener --> agent_reply;
	send_discord --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const DISCORD_PRIVATE_LISTENER_WORKFLOW: Workflow = {
  id: "template-discord-private-listener",
  name: "Discord Private Listener",
  description:
    "Receives Discord bot messages over the Gateway, generates a reply with AgentNode, and sends it back through MessageDiscordNode.",
  createdAt: "2026-03-11T12:00:00Z",
  updatedAt: "2026-03-11T12:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "discord", "listener", "agent"],
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
      id: "discord_listener",
      type: "trigger",
      position: { x: 250, y: 0 },
      data: {
        label: "DiscordBotListenerNode",
        type: "trigger",
        backendType: "DiscordBotListenerNode",
        description: "Normalizes Discord listener events for downstream nodes.",
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
          "Generates the Discord reply text from the listener event.",
      },
    },
    {
      id: "send_discord",
      type: "messaging",
      position: { x: 800, y: 0 },
      data: {
        label: "MessageDiscordNode",
        type: "messaging",
        backendType: "MessageDiscordNode",
        description: "Sends the AgentNode reply back to the Discord channel.",
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
      target: "discord_listener",
    },
    {
      id: "edge-listener-agent",
      source: "discord_listener",
      target: "agent_reply",
    },
    {
      id: "edge-agent-send",
      source: "agent_reply",
      target: "send_discord",
    },
    {
      id: "edge-send-end",
      source: "send_discord",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-discord-private-listener-v1",
      mermaid: DISCORD_PRIVATE_LISTENER_MERMAID,
    },
  ],
};

export const DISCORD_PRIVATE_LISTENER_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: DISCORD_PRIVATE_LISTENER_WORKFLOW,
  script: discordPrivateListenerScript,
  runnableConfig: discordPrivateListenerConfig,
  notes: "Seeded from Discord Private Listener template.",
  metadata: {
    templateVersion: "1.0.0",
    minOrcheoVersion: "0.1.0",
    validatedProviderApi: "discord-gateway-v10",
    validationDate: "2026-03-11",
    owner: "Shaojie Jiang",
    acceptanceCriteria: [
      "Imports into Canvas without manual edits.",
      "Runs DiscordBotListenerNode -> AgentNode -> MessageDiscordNode end to end.",
      "Documents required credentials and provider/API compatibility.",
    ],
    revalidationTriggers: [
      "Discord Gateway major version change",
      "MessageDiscordNode contract change",
      "Listener runtime contract change",
    ],
    replyNodeContracts: ["MessageDiscordNode@1"],
  },
};
