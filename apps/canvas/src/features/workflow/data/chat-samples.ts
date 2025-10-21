import type { ChatKitSession } from "@features/shared/components/chatkit/types";

const isoMinutesAgo = (minutesAgo: number) =>
  new Date(Date.now() - minutesAgo * 60_000).toISOString();

const baseAssistant = {
  id: "assistant-default",
  name: "Workflow Copilot",
  avatar: "https://avatar.vercel.sh/workflow-copilot",
  isAI: true,
} as const;

const baseUser = {
  id: "workflow-owner",
  name: "Workflow Owner",
  avatar: "https://avatar.vercel.sh/workflow-owner",
};

export const SAMPLE_CHAT_SESSIONS: ChatKitSession[] = [
  {
    id: "handoff-production",
    nodeId: "chat-trigger-production",
    title: "Launch campaign handoff",
    subtitle: "Marketing automation • Production",
    description:
      "Production chat room for the marketing launch workflow hand-off.",
    environment: "production",
    status: "handoff-ready",
    pinned: true,
    updatedAt: isoMinutesAgo(5),
    participants: [
      {
        id: baseUser.id,
        name: baseUser.name,
        avatar: baseUser.avatar,
        role: "user",
      },
      {
        id: baseAssistant.id,
        name: baseAssistant.name,
        avatar: baseAssistant.avatar,
        role: "ai",
      },
      {
        id: "qa-lead",
        name: "Morgan Patel",
        avatar: "https://avatar.vercel.sh/morgan",
        role: "reviewer",
      },
    ],
    quickPrompts: [
      "Summarize the last production run",
      "List launch blockers",
      "Generate customer-ready status update",
    ],
    handoffChecklist: [
      {
        id: "handoff-copy-review",
        label: "Final content reviewed and approved",
        completed: true,
        owner: "Morgan Patel",
      },
      {
        id: "handoff-credentials",
        label: "Credential scope validated for production use",
        completed: true,
        owner: "Workflow Owner",
      },
      {
        id: "handoff-monitoring",
        label: "Monitoring alerts configured for launch window",
        completed: false,
        owner: "SRE Rotation",
        dueDate: "Today",
      },
    ],
    runSummaries: [
      {
        id: "prod-run-42",
        status: "completed",
        environment: "production",
        startedAt: isoMinutesAgo(32),
        durationMs: 4820,
        triggeredBy: "Workflow Owner",
        tokens: { prompt: 612, completion: 318, total: 930 },
        notes: "Validated launch assets and distributed Slack announcement.",
      },
    ],
    tokenEstimate: { prompt: 640, completion: 340, total: 980 },
    messages: [
      {
        id: "handoff-1",
        content:
          "Production run completed successfully. All launch emails queued and approvals stored in the audit log.",
        sender: baseAssistant,
        timestamp: isoMinutesAgo(40),
      },
      {
        id: "handoff-2",
        content:
          "Great — can you surface any remaining blockers before we flip the switch?",
        sender: baseUser,
        timestamp: isoMinutesAgo(38),
        isUserMessage: true,
      },
      {
        id: "handoff-3",
        content:
          "Only pending item is confirming the monitoring webhook is active. Once that's done I'll mark the hand-off as complete.",
        sender: baseAssistant,
        timestamp: isoMinutesAgo(36),
      },
      {
        id: "handoff-4",
        content:
          "Monitoring alert is now configured. Ready for final approval.",
        sender: baseUser,
        timestamp: isoMinutesAgo(6),
        isUserMessage: true,
      },
    ],
  },
  {
    id: "draft-playground",
    nodeId: "chat-trigger-draft",
    title: "Workflow playground",
    subtitle: "Draft environment",
    description:
      "Sandbox chat for iterating on prompts and flows before publish.",
    environment: "draft",
    status: "running",
    pinned: false,
    updatedAt: isoMinutesAgo(1),
    participants: [
      {
        id: baseUser.id,
        name: baseUser.name,
        avatar: baseUser.avatar,
        role: "user",
      },
      {
        id: baseAssistant.id,
        name: baseAssistant.name,
        avatar: baseAssistant.avatar,
        role: "ai",
      },
    ],
    quickPrompts: [
      "Trigger a draft run",
      "Show me token usage",
      "What changed since the last iteration?",
    ],
    handoffChecklist: [
      {
        id: "draft-validation",
        label: "Validate credential assignment for chat trigger",
        completed: false,
        owner: "Workflow Owner",
      },
      {
        id: "draft-copy",
        label: "QA welcome prompt copy",
        completed: false,
        owner: "Content Team",
      },
    ],
    runSummaries: [
      {
        id: "draft-run-13",
        status: "running",
        environment: "draft",
        startedAt: isoMinutesAgo(2),
        triggeredBy: "Workflow Owner",
        tokens: { prompt: 280, completion: 144, total: 424 },
        notes: "Testing new prompt variations for onboarding flow.",
      },
    ],
    tokenEstimate: { prompt: 300, completion: 150, total: 450 },
    messages: [
      {
        id: "draft-1",
        content:
          "Draft run kicked off. I'll post token stats once the loop completes.",
        sender: baseAssistant,
        timestamp: isoMinutesAgo(3),
      },
      {
        id: "draft-2",
        content:
          "Log the latest prompt deltas and check whether we need additional approvals before publish.",
        sender: baseUser,
        timestamp: isoMinutesAgo(2),
        isUserMessage: true,
      },
      {
        id: "draft-3",
        content:
          "Documented the prompt changes. Credential scope is limited to sandbox tokens; no extra approval required yet.",
        sender: baseAssistant,
        timestamp: isoMinutesAgo(1),
      },
    ],
  },
];
