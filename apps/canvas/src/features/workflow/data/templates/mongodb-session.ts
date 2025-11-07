import { Workflow } from "../workflow-types";
import { TEMPLATE_OWNER } from "./template-owner";

export const MONGODB_SESSION_WORKFLOW: Workflow = {
  id: "workflow-mongodb-session",
  name: "MongoDB Query Session",
  description: "Demonstrates MongoDB node reuse across runs.",
  createdAt: "2024-02-18T16:10:00Z",
  updatedAt: "2024-03-05T19:55:00Z",
  sourceExample: "examples/mongodb.py",
  owner: TEMPLATE_OWNER,
  tags: ["template", "database", "storage"],
  nodes: [
    {
      id: "mongodb-start",
      type: "start",
      position: { x: 0, y: 0 },
      data: {
        label: "Start",
        type: "start",
        description: "Start the MongoDB query workflow.",
      },
    },
    {
      id: "mongodb-query",
      type: "data",
      position: { x: 260, y: 0 },
      data: {
        label: "Query MongoDB collection",
        type: "data",
        description:
          "MongoDB node performs a find operation using the configured session.",
        examplePath: "examples/mongodb.py",
      },
    },
    {
      id: "mongodb-end",
      type: "end",
      position: { x: 520, y: 0 },
      data: {
        label: "Finish",
        type: "end",
        description: "Workflow ends after retrieving the MongoDB results.",
      },
    },
  ],
  edges: [
    {
      id: "edge-mongodb-start-query",
      source: "mongodb-start",
      target: "mongodb-query",
    },
    {
      id: "edge-mongodb-query-end",
      source: "mongodb-query",
      target: "mongodb-end",
    },
  ],
};
