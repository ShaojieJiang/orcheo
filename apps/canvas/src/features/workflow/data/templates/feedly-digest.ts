import { Workflow } from "../workflow-types";
import { TEMPLATE_OWNER } from "./template-owner";

export const FEEDLY_DIGEST_WORKFLOW: Workflow = {
  id: "workflow-feedly-digest",
  name: "Feedly Digest to Telegram",
  description:
    "Captures a Feedly token, fetches unread items, and sends a Telegram digest.",
  createdAt: "2024-01-22T09:10:00Z",
  updatedAt: "2024-03-07T12:05:00Z",
  sourceExample: "examples/feedly_news.py",
  owner: TEMPLATE_OWNER,
  tags: ["template", "news", "telegram", "automation"],
  lastRun: {
    status: "success",
    timestamp: "2024-03-08T05:00:00Z",
    duration: 57.8,
  },
  nodes: [
    {
      id: "feedly-start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Kick off the Feedly news digest workflow.",
      },
    },
    {
      id: "collect-feedly-token",
      type: "function",
      position: { x: 220, y: 0 },
      data: {
        label: "Collect Feedly token",
        type: "function",
        description: "Browser automation retrieves the Feedly developer token.",
        examplePath: "examples/feedly_news.py",
      },
    },
    {
      id: "fetch-unread-articles",
      type: "api",
      position: { x: 440, y: 0 },
      data: {
        label: "Fetch unread articles",
        type: "api",
        description:
          "HTTP request pulls unread articles and formats them for Telegram.",
        examplePath: "examples/feedly_news.py",
      },
    },
    {
      id: "send-telegram-digest",
      type: "api",
      position: { x: 660, y: 0 },
      data: {
        label: "Send Telegram digest",
        type: "api",
        description:
          "MessageTelegram sends the formatted digest to the configured chat.",
        examplePath: "examples/feedly_news.py",
      },
    },
    {
      id: "mark-as-read",
      type: "api",
      position: { x: 660, y: 160 },
      data: {
        label: "Mark entries as read",
        type: "api",
        description: "Optional HTTP call updates Feedly with the read status.",
        isDisabled: true,
        examplePath: "examples/feedly_news.py",
      },
    },
    {
      id: "feedly-end",
      type: "end",
      position: { x: 880, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Workflow completes after sending notifications.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-token",
      source: "feedly-start",
      target: "collect-feedly-token",
    },
    {
      id: "edge-token-fetch",
      source: "collect-feedly-token",
      target: "fetch-unread-articles",
    },
    {
      id: "edge-fetch-telegram",
      source: "fetch-unread-articles",
      target: "send-telegram-digest",
    },
    {
      id: "edge-telegram-end",
      source: "send-telegram-digest",
      target: "feedly-end",
    },
    {
      id: "edge-telegram-mark",
      source: "send-telegram-digest",
      target: "mark-as-read",
    },
    {
      id: "edge-mark-end",
      source: "mark-as-read",
      target: "feedly-end",
    },
  ],
};
