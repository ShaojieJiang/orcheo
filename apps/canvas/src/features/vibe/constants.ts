import type { ExternalAgentProviderName } from "@/lib/api";

export const VIBE_SIDEBAR_WIDTH = 400;
export const VIBE_SIDEBAR_MIN_WIDTH = 300;
export const VIBE_SIDEBAR_MAX_WIDTH = 600;
export const VIBE_SIDEBAR_COLLAPSED_WIDTH = 48;

export const VIBE_AGENT_TAG = "orcheo-vibe-agent";

export const VIBE_AGENT_POLL_INTERVAL_MS = 30_000;

interface VibeAgentMapping {
  templateId: string;
  workflowName: string;
  displayName: string;
}

export const VIBE_AGENT_MAPPINGS: Record<
  ExternalAgentProviderName,
  VibeAgentMapping
> = {
  claude_code: {
    templateId: "template-claude-code-agent",
    workflowName: "Orcheo Claude Code",
    displayName: "Claude Code",
  },
  codex: {
    templateId: "template-codex-agent",
    workflowName: "Orcheo Codex",
    displayName: "Codex",
  },
  gemini: {
    templateId: "template-gemini-agent",
    workflowName: "Orcheo Gemini",
    displayName: "Gemini",
  },
};
