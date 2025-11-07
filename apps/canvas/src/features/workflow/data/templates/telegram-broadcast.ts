import { Workflow } from "../workflow-types";
import { TEMPLATE_OWNER } from "./template-owner";

export const TELEGRAM_BROADCAST_WORKFLOW: Workflow = {
  id: "workflow-telegram-broadcast",
  name: "Python to Telegram Broadcast",
  description: "Generates a message in Python and forwards it to Telegram.",
  createdAt: "2024-02-24T21:00:00Z",
  updatedAt: "2024-03-08T09:30:00Z",
  sourceExample: "examples/telegram_example.py",
  owner: TEMPLATE_OWNER,
  tags: ["template", "telegram", "python"],
  nodes: [
    {
      id: "telegram-start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for the Telegram broadcast.",
      },
    },
    {
      id: "compose-telegram-message",
      type: "function",
      position: { x: 220, y: 0 },
      data: {
        label: "Compose message with Python",
        type: "function",
        description:
          "PythonCode node prepares the message payload for Telegram.",
        examplePath: "examples/telegram_example.py",
      },
    },
    {
      id: "send-telegram-message",
      type: "api",
      position: { x: 440, y: 0 },
      data: {
        label: "Send Telegram message",
        type: "api",
        description:
          "MessageTelegram node sends the composed message to the target chat.",
        examplePath: "examples/telegram_example.py",
      },
    },
    {
      id: "telegram-end",
      type: "end",
      position: { x: 660, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Broadcast completed successfully.",
      },
    },
  ],
  edges: [
    {
      id: "edge-telegram-start-compose",
      source: "telegram-start",
      target: "compose-telegram-message",
    },
    {
      id: "edge-telegram-compose-send",
      source: "compose-telegram-message",
      target: "send-telegram-message",
    },
    {
      id: "edge-telegram-send-end",
      source: "send-telegram-message",
      target: "telegram-end",
    },
  ],
};
