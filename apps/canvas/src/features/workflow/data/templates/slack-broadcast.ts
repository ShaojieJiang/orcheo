import { Workflow } from "../workflow-types";
import { TEMPLATE_OWNER } from "./template-owner";

export const SLACK_BROADCAST_WORKFLOW: Workflow = {
  id: "workflow-slack-broadcast",
  name: "Slack Channel Broadcast",
  description: "Posts an announcement to a Slack channel.",
  createdAt: "2024-02-01T13:20:00Z",
  updatedAt: "2024-03-02T18:40:00Z",
  sourceExample: "examples/slack.py",
  owner: TEMPLATE_OWNER,
  tags: ["template", "slack", "messaging"],
  nodes: [
    {
      id: "slack-start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Begin the Slack announcement workflow.",
      },
    },
    {
      id: "send-slack-message",
      type: "api",
      position: { x: 260, y: 0 },
      data: {
        label: "Send Slack message",
        type: "api",
        description: "Slack node posts the message to the configured channel.",
        examplePath: "examples/slack.py",
      },
    },
    {
      id: "slack-end",
      type: "end",
      position: { x: 520, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Slack announcement has been delivered.",
      },
    },
  ],
  edges: [
    {
      id: "edge-slack-start-send",
      source: "slack-start",
      target: "send-slack-message",
    },
    {
      id: "edge-slack-end",
      source: "send-slack-message",
      target: "slack-end",
    },
  ],
};
