import type { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import telegramHelloScript from "./assets/telegram-hello/workflow.py?raw";

const TELEGRAM_HELLO_MERMAID = `---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>START</p>]):::first
	send_telegram_hello(send_telegram_hello)
	__end__([<p>END</p>]):::last
	__start__ --> send_telegram_hello;
	send_telegram_hello --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
`;

export const TELEGRAM_HELLO_WORKFLOW: Workflow = {
  id: "template-telegram-hello",
  name: "Telegram Hello",
  description:
    "Sends a simple Hello message to Telegram using vault-backed placeholders.",
  createdAt: "2026-03-10T09:00:00Z",
  updatedAt: "2026-03-10T09:00:00Z",
  sourceExample: "examples/telegram_example.py",
  owner: TEMPLATE_OWNER,
  tags: ["template", "python", "telegram"],
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for the workflow run.",
      },
    },
    {
      id: "send_telegram_hello",
      type: "telegram",
      position: { x: 280, y: 0 },
      data: {
        label: "MessageTelegramNode",
        type: "telegram",
        description:
          "Sends the fixed Hello message to the configured Telegram chat.",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 560, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Workflow completes after the Telegram message is sent.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-telegram",
      source: "start",
      target: "send_telegram_hello",
    },
    {
      id: "edge-telegram-end",
      source: "send_telegram_hello",
      target: "end",
    },
  ],
  versions: [
    {
      id: "template-telegram-hello-v1",
      mermaid: TELEGRAM_HELLO_MERMAID,
    },
  ],
};

export const TELEGRAM_HELLO_TEMPLATE: WorkflowTemplateDefinition = {
  workflow: TELEGRAM_HELLO_WORKFLOW,
  script: telegramHelloScript,
  notes: "Seeded from Telegram Hello template.",
};
