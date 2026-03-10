import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import telegramHeartbeatConfig from "./assets/telegram-heartbeat/config.json";
import telegramHeartbeatScript from "./assets/telegram-heartbeat/workflow.py?raw";

const TELEGRAM_HEARTBEAT_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	cron_trigger(cron_trigger)
	send_heartbeat(send_heartbeat)
	__end__([<p>END</p>]):::last
	__start__ --> cron_trigger;
	cron_trigger --> send_heartbeat;
	send_heartbeat --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const TELEGRAM_HEARTBEAT_WORKFLOW: Workflow = {
  id: "template-telegram-heartbeat",
  name: "Telegram Heartbeat",
  description:
    "Runs every minute with a cron trigger and sends a heartbeat message to Telegram.",
  createdAt: "2026-03-10T13:00:00Z",
  updatedAt: "2026-03-10T13:00:00Z",
  owner: TEMPLATE_OWNER,
  tags: ["template", "python", "telegram", "trigger"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for the scheduled workflow run.",
      },
    },
    {
      id: "cron_trigger",
      type: "trigger",
      position: { x: 260, y: 0 },
      data: {
        label: "CronTriggerNode",
        type: "trigger",
        backendType: "CronTriggerNode",
        description: "Triggers the workflow every minute.",
        expression: "* * * * *",
        timezone: "UTC",
        allow_overlapping: true,
      },
    },
    {
      id: "send_heartbeat",
      type: "telegram",
      position: { x: 520, y: 0 },
      data: {
        label: "MessageTelegram",
        type: "telegram",
        description: "Sends the configured heartbeat message to Telegram.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 780, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Workflow completes after the heartbeat is sent.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-cron",
      source: "start",
      target: "cron_trigger",
    },
    {
      id: "edge-cron-telegram",
      source: "cron_trigger",
      target: "send_heartbeat",
    },
    {
      id: "edge-telegram-end",
      source: "send_heartbeat",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-telegram-heartbeat-v1",
      mermaid: TELEGRAM_HEARTBEAT_MERMAID,
    },
  ],
};

export const TELEGRAM_HEARTBEAT_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: TELEGRAM_HEARTBEAT_WORKFLOW,
  script: telegramHeartbeatScript,
  runnableConfig: telegramHeartbeatConfig,
  notes: "Seeded from Telegram Heartbeat template.",
};
