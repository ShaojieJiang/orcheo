import type { SubworkflowStructure } from "./types";

export const incidentResponseSubworkflow: SubworkflowStructure = {
  nodes: [
    {
      id: "incident-raised",
      type: "trigger",
      position: { x: 0, y: 0 },
      data: {
        type: "trigger",
        label: "PagerDuty incident raised",
        description: "Triggered when a Sev1 alert fires.",
        status: "idle",
      },
    },
    {
      id: "triage-severity",
      type: "function",
      position: { x: 260, y: 0 },
      data: {
        type: "function",
        label: "Triage severity",
        description: "Evaluate runbooks and required responders.",
        status: "idle",
      },
    },
    {
      id: "notify-oncall",
      type: "api",
      position: { x: 520, y: -120 },
      data: {
        type: "api",
        label: "Notify on-call",
        description: "Post critical details into the on-call channel.",
        status: "idle",
      },
    },
    {
      id: "escalate-leads",
      type: "api",
      position: { x: 520, y: 120 },
      data: {
        type: "api",
        label: "Escalate to leads",
        description: "Escalate if no acknowledgement within SLA.",
        status: "idle",
      },
    },
    {
      id: "update-status",
      type: "function",
      position: { x: 780, y: 0 },
      data: {
        type: "function",
        label: "Update status page",
        description: "Publish current impact for stakeholders.",
        status: "idle",
      },
    },
  ],
  edges: [
    {
      id: "edge-raised-triage",
      source: "incident-raised",
      target: "triage-severity",
    },
    {
      id: "edge-triage-notify",
      source: "triage-severity",
      target: "notify-oncall",
    },
    {
      id: "edge-triage-escalate",
      source: "triage-severity",
      target: "escalate-leads",
    },
    {
      id: "edge-notify-update",
      source: "notify-oncall",
      target: "update-status",
    },
    {
      id: "edge-escalate-update",
      source: "escalate-leads",
      target: "update-status",
    },
  ],
};
