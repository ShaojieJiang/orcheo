import type { SubworkflowStructure } from "./types";

export const contentQaSubworkflow: SubworkflowStructure = {
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
};
