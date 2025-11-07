import { Workflow } from "../workflow-types";
import { TEMPLATE_OWNER } from "./template-owner";

export const QUICKSTART_WELCOME_WORKFLOW: Workflow = {
  id: "workflow-quickstart",
  name: "Canvas Quickstart — Welcome Bot",
  description:
    "Greets a new teammate with a PythonCode node and saves the message to the canvas flow.",
  createdAt: "2024-01-15T10:00:00Z",
  updatedAt: "2024-03-04T15:30:00Z",
  sourceExample: "examples/quickstart/canvas_welcome.json",
  owner: TEMPLATE_OWNER,
  tags: ["template", "quickstart", "canvas"],
  lastRun: {
    status: "success",
    timestamp: "2024-03-05T08:45:00Z",
    duration: 3.1,
  },
  nodes: [
    {
      id: "start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Entry point for the welcome flow.",
      },
    },
    {
      id: "compose-welcome-message",
      type: "function",
      position: { x: 260, y: 0 },
      data: {
        label: "Compose welcome message",
        type: "function",
        description:
          "PythonCode node returns a templated greeting for the new teammate.",
        examplePath: "examples/quickstart/canvas_welcome.json",
      },
    },
    {
      id: "end",
      type: "end",
      position: { x: 520, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Flow completes after crafting the welcome message.",
      },
    },
  ],
  edges: [
    {
      id: "edge-start-compose",
      source: "start",
      target: "compose-welcome-message",
    },
    {
      id: "edge-compose-end",
      source: "compose-welcome-message",
      target: "end",
    },
  ],
};
