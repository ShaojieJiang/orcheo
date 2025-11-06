import type { SubworkflowStructure } from "./types";

export const customerOnboardingSubworkflow: SubworkflowStructure = {
  nodes: [
    {
      id: "capture-intake",
      type: "trigger",
      position: { x: 0, y: 0 },
      data: {
        type: "trigger",
        label: "Capture intake request",
        description: "Webhook triggered when a signup is submitted.",
        status: "idle",
      },
    },
    {
      id: "enrich-profile",
      type: "function",
      position: { x: 260, y: 0 },
      data: {
        type: "function",
        label: "Enrich CRM profile",
        description: "Collect firmographic data for the new customer.",
        status: "idle",
      },
    },
    {
      id: "provision-access",
      type: "api",
      position: { x: 520, y: 0 },
      data: {
        type: "api",
        label: "Provision access",
        description: "Create accounts across internal and SaaS tools.",
        status: "idle",
      },
    },
    {
      id: "send-welcome",
      type: "api",
      position: { x: 780, y: 0 },
      data: {
        type: "api",
        label: "Send welcome sequence",
        description: "Kick off emails, docs, and success team handoff.",
        status: "idle",
      },
    },
  ],
  edges: [
    {
      id: "edge-capture-enrich",
      source: "capture-intake",
      target: "enrich-profile",
    },
    {
      id: "edge-enrich-provision",
      source: "enrich-profile",
      target: "provision-access",
    },
    {
      id: "edge-provision-welcome",
      source: "provision-access",
      target: "send-welcome",
    },
  ],
};
