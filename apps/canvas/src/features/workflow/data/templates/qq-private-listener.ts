import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import qqPrivateListenerConfig from "./assets/qq-private-listener/config.json";
import qqPrivateListenerScript from "./assets/qq-private-listener/workflow.py?raw";

const QQ_PRIVATE_LISTENER_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	root__start(["START"]):::first
	root__node__qq_listener["QQBotListenerNode"]
	root__node__agent_reply["AgentNode"]
	root__node__send_qq["MessageQQNode"]
	root__end(["END"]):::last
	root__start --> root__node__qq_listener;
	root__node__qq_listener --> root__node__agent_reply;
	root__node__agent_reply --> root__node__send_qq;
	root__node__send_qq --> root__end;
	classDef default fill:#eef4ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#94b8ff
`;

export const QQ_PRIVATE_LISTENER_WORKFLOW: Workflow = {
  id: "template-qq-private-listener",
  name: "QQ Private Listener",
  description:
    "Receives QQ bot messages over the Gateway, generates a reply with AgentNode, and sends it back through MessageQQNode.",
  createdAt: "2026-03-11T12:00:00Z",
  updatedAt: "2026-03-11T12:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "qq", "listener", "agent"],
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
      id: "qq_listener",
      type: "trigger",
      position: { x: 250, y: 0 },
      data: {
        label: "QQBotListenerNode",
        type: "trigger",
        backendType: "QQBotListenerNode",
        description: "Normalizes QQ listener events for downstream nodes.",
      },
    },
    {
      id: "agent_reply",
      type: "agent",
      position: { x: 520, y: 0 },
      data: {
        label: "AgentNode",
        type: "agent",
        description: "Generates the QQ reply text from the listener event.",
      },
    },
    {
      id: "send_qq",
      type: "messaging",
      position: { x: 800, y: 0 },
      data: {
        label: "MessageQQNode",
        type: "messaging",
        backendType: "MessageQQNode",
        description: "Sends the AgentNode reply back to the QQ scene.",
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
      target: "qq_listener",
    },
    {
      id: "edge-listener-agent",
      source: "qq_listener",
      target: "agent_reply",
    },
    {
      id: "edge-agent-send",
      source: "agent_reply",
      target: "send_qq",
    },
    {
      id: "edge-send-end",
      source: "send_qq",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-qq-private-listener-v1",
      mermaid: QQ_PRIVATE_LISTENER_MERMAID,
    },
  ],
};

export const QQ_PRIVATE_LISTENER_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: QQ_PRIVATE_LISTENER_WORKFLOW,
  script: qqPrivateListenerScript,
  runnableConfig: qqPrivateListenerConfig,
  notes: "Seeded from QQ Private Listener template.",
  metadata: {
    templateVersion: "1.0.0",
    minOrcheoVersion: "0.1.0",
    validatedProviderApi: "qq-bot-api-v2",
    validationDate: "2026-03-11",
    owner: "Shaojie Jiang",
    acceptanceCriteria: [
      "Imports into Canvas without manual edits.",
      "Runs QQBotListenerNode -> AgentNode -> MessageQQNode end to end.",
      "Documents required credentials and provider/API compatibility.",
    ],
    revalidationTriggers: [
      "QQ Bot API v2 major version change",
      "MessageQQNode contract change",
      "Listener runtime contract change",
    ],
    replyNodeContracts: ["MessageQQNode@1"],
  },
};
