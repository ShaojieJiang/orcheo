import type {
  WorkflowEdge as PersistedWorkflowEdge,
  WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";

export type SubworkflowStructure = {
  nodes: PersistedWorkflowNode[];
  edges: PersistedWorkflowEdge[];
};

export const SUBWORKFLOW_LIBRARY: Record<string, SubworkflowStructure> = {
  "subflow-customer-onboarding": {
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
  },
  "subflow-incident-response": {
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
  },
  "subflow-content-qa": {
    nodes: [
      {
        id: "draft-ready",
        type: "trigger",
        position: { x: 0, y: 0 },
        data: {
          type: "trigger",
          label: "Draft ready for review",
          description: "Start QA once an AI draft is submitted.",
          status: "idle",
        },
      },
      {
        id: "score-quality",
        type: "ai",
        position: { x: 260, y: 0 },
        data: {
          type: "ai",
          label: "Score quality",
          description: "Use AI rubric to score voice, tone, and accuracy.",
          status: "idle",
        },
      },
      {
        id: "collect-feedback",
        type: "function",
        position: { x: 520, y: -120 },
        data: {
          type: "function",
          label: "Collect revisions",
          description: "Request edits from stakeholders when needed.",
          status: "idle",
        },
      },
      {
        id: "schedule-publish",
        type: "api",
        position: { x: 520, y: 120 },
        data: {
          type: "api",
          label: "Schedule publish",
          description: "Queue approved content in the CMS calendar.",
          status: "idle",
        },
      },
      {
        id: "final-approval",
        type: "function",
        position: { x: 780, y: 0 },
        data: {
          type: "function",
          label: "Finalize and log",
          description: "Capture QA notes and mark the run complete.",
          status: "idle",
        },
      },
    ],
    edges: [
      {
        id: "edge-draft-score",
        source: "draft-ready",
        target: "score-quality",
      },
      {
        id: "edge-score-feedback",
        source: "score-quality",
        target: "collect-feedback",
      },
      {
        id: "edge-score-schedule",
        source: "score-quality",
        target: "schedule-publish",
      },
      {
        id: "edge-feedback-final",
        source: "collect-feedback",
        target: "final-approval",
      },
      {
        id: "edge-schedule-final",
        source: "schedule-publish",
        target: "final-approval",
      },
    ],
  },
};
