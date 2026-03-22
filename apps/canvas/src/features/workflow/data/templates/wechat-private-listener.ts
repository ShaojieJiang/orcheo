import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import wechatPrivateListenerConfig from "./assets/wechat-private-listener/config.json";
import wechatPrivateListenerScript from "./assets/wechat-private-listener/workflow.py?raw";

const WECHAT_PRIVATE_LISTENER_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	wechat_listener(wechat_listener)
	agent_reply(agent_reply)
	extract_reply(extract_reply)
	send_wechat(send_wechat)
	__end__([<p>END</p>]):::last
	__start__ --> wechat_listener;
	agent_reply --> extract_reply;
	extract_reply --> send_wechat;
	wechat_listener --> agent_reply;
	send_wechat --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const WECHAT_PRIVATE_LISTENER_WORKFLOW: Workflow = {
  id: "template-wechat-private-listener",
  name: "WeChat Private Listener",
  description:
    "Receives WeChat messages through the WeChat listener plugin, generates a reply with AgentNode, and sends it back through WechatReplyNode.",
  createdAt: "2026-03-22T12:00:00Z",
  updatedAt: "2026-03-22T12:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "wechat", "listener", "plugin", "agent"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Workflow entry point for WeChat listener-triggered runs.",
      },
    },
    {
      id: "wechat_listener",
      type: "trigger",
      position: { x: 260, y: 0 },
      data: {
        label: "WechatListenerPluginNode",
        type: "trigger",
        backendType: "WechatListenerPluginNode",
        description:
          "Receives WeChat events through the external WeChat listener plugin.",
      },
    },
    {
      id: "agent_reply",
      type: "agent",
      position: { x: 540, y: 0 },
      data: {
        label: "AgentNode",
        type: "agent",
        description: "Generates the reply text for the inbound WeChat message.",
      },
    },
    {
      id: "extract_reply",
      type: "utility",
      position: { x: 820, y: 0 },
      data: {
        label: "AgentReplyExtractorNode",
        type: "utility",
        backendType: "AgentReplyExtractorNode",
        description:
          "Extracts the final assistant reply text for WechatReplyNode.",
      },
    },
    {
      id: "send_wechat",
      type: "messaging",
      position: { x: 1100, y: 0 },
      data: {
        label: "WechatReplyNode",
        type: "messaging",
        backendType: "WechatReplyNode",
        description:
          "Sends the extracted reply back through the WeChat plugin HTTP API.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 1380, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "The WeChat listener-triggered reply flow completes here.",
      },
    },
  ],
  edges: [
    { id: "edge-start-listener", source: "start", target: "wechat_listener" },
    {
      id: "edge-listener-agent",
      source: "wechat_listener",
      target: "agent_reply",
    },
    {
      id: "edge-agent-extract",
      source: "agent_reply",
      target: "extract_reply",
    },
    {
      id: "edge-extract-send",
      source: "extract_reply",
      target: "send_wechat",
    },
    { id: "edge-send-end", source: "send_wechat", target: "end" },
  ],
  versions: [
    {
      id: "template-wechat-private-listener-v1",
      mermaid: WECHAT_PRIVATE_LISTENER_MERMAID,
    },
  ],
};

export const WECHAT_PRIVATE_LISTENER_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: WECHAT_PRIVATE_LISTENER_WORKFLOW,
  script: wechatPrivateListenerScript,
  runnableConfig: wechatPrivateListenerConfig,
  notes: "Seeded from the WeChat private listener plugin template.",
  metadata: {
    templateVersion: "1.0.0",
    minOrcheoVersion: "0.1.0",
    validatedProviderApi: "openclaw-wechat-plugin-2026-03-22",
    validationDate: "2026-03-22",
    owner: "Shaojie Jiang",
    requiredPlugins: ["orcheo-plugin-wechat-listener"],
    acceptanceCriteria: [
      "Imports into Canvas once the WeChat listener plugin is installed.",
      "Compiles a valid WeChat listener subscription from the plugin-backed workflow.",
      "Runs WechatListenerPluginNode -> AgentNode -> AgentReplyExtractorNode -> WechatReplyNode.",
    ],
    revalidationTriggers: [
      "WeChat listener plugin contract change",
      "WechatReplyNode or AgentReplyExtractorNode contract change",
      "OpenClaw WeChat API contract change",
      "Canvas template import contract change",
    ],
    replyNodeContracts: ["WechatReplyNode@1"],
  },
};
