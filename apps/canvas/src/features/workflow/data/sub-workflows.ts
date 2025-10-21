import type { WorkflowEdge, WorkflowNode } from "./workflow-data";

export interface ReusableSubWorkflow {
  id: string;
  name: string;
  description: string;
  category: "automation" | "ai" | "data" | "communication";
  tags: string[];
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

const createNode = (
  id: string,
  type: WorkflowNode["type"],
  x: number,
  y: number,
  data: WorkflowNode["data"],
): WorkflowNode => ({
  id,
  type,
  position: { x, y },
  data,
});

export const REUSABLE_SUB_WORKFLOWS: ReusableSubWorkflow[] = [
  {
    id: "sub-qualify-lead",
    name: "Qualify lead and sync to CRM",
    description:
      "Enrich an inbound lead, score it with AI, and update the CRM when ready for sales.",
    category: "automation",
    tags: ["leads", "crm", "routing"],
    nodes: [
      createNode("node-1", "trigger", 0, 0, {
        label: "Inbound Lead",
        type: "trigger",
        description: "Triggered when a new lead submits the form",
      }),
      createNode("node-2", "api", 260, 0, {
        label: "Enrich Profile",
        type: "api",
        description: "Fetch company and persona data",
      }),
      createNode("node-3", "ai", 520, 0, {
        label: "Score Lead",
        type: "ai",
        description: "Use GPT to score buying intent",
      }),
      createNode("node-4", "api", 780, 0, {
        label: "Update CRM",
        type: "api",
        description: "Create or update opportunity in CRM",
      }),
    ],
    edges: [
      { id: "edge-1", source: "node-1", target: "node-2" },
      { id: "edge-2", source: "node-2", target: "node-3" },
      { id: "edge-3", source: "node-3", target: "node-4" },
    ],
  },
  {
    id: "sub-meeting-summary",
    name: "Meeting insights summary",
    description:
      "Transcribe a call, extract action items, and send a summary to stakeholders.",
    category: "communication",
    tags: ["meetings", "summaries", "notifications"],
    nodes: [
      createNode("node-1", "trigger", 0, 0, {
        label: "New Recording",
        type: "trigger",
        description: "Triggered when a call recording is available",
      }),
      createNode("node-2", "ai", 260, 0, {
        label: "Transcribe Audio",
        type: "ai",
        description: "Convert call audio into text",
      }),
      createNode("node-3", "function", 520, 0, {
        label: "Extract Actions",
        type: "function",
        description: "Identify owners and due dates",
      }),
      createNode("node-4", "api", 780, 0, {
        label: "Send Recap",
        type: "api",
        description: "Email summary to attendees",
      }),
    ],
    edges: [
      { id: "edge-1", source: "node-1", target: "node-2" },
      { id: "edge-2", source: "node-2", target: "node-3" },
      { id: "edge-3", source: "node-3", target: "node-4" },
    ],
  },
  {
    id: "sub-sync-warehouse",
    name: "Sync metrics to warehouse",
    description:
      "Pull metrics from analytics API, transform them, and load into the warehouse.",
    category: "data",
    tags: ["analytics", "warehouse", "etl"],
    nodes: [
      createNode("node-1", "trigger", 0, 0, {
        label: "Nightly Schedule",
        type: "trigger",
        description: "Run every night at midnight",
      }),
      createNode("node-2", "api", 260, 0, {
        label: "Fetch Metrics",
        type: "api",
        description: "Call analytics API",
      }),
      createNode("node-3", "data", 520, 0, {
        label: "Normalize Dataset",
        type: "data",
        description: "Clean and normalize records",
      }),
      createNode("node-4", "api", 780, 0, {
        label: "Load to Warehouse",
        type: "api",
        description: "Insert rows into warehouse",
      }),
    ],
    edges: [
      { id: "edge-1", source: "node-1", target: "node-2" },
      { id: "edge-2", source: "node-2", target: "node-3" },
      { id: "edge-3", source: "node-3", target: "node-4" },
    ],
  },
];
