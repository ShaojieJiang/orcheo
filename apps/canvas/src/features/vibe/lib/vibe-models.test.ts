import { describe, expect, it } from "vitest";
import type { ExternalAgentProviderStatus } from "@/lib/api";
import {
  buildVibeComposerModels,
  buildVibeSupportedModels,
  getDefaultVibeProviderName,
} from "./vibe-models";

const buildProvider = (
  provider: ExternalAgentProviderStatus["provider"],
  displayName: string,
): ExternalAgentProviderStatus => ({
  provider,
  display_name: displayName,
  state: "ready",
  installed: true,
  authenticated: true,
  supports_oauth: true,
  resolved_version: "1.0.0",
  executable_path: `/tmp/${provider}`,
  checked_at: "2026-04-13T10:00:00Z",
  last_auth_ok_at: "2026-04-13T10:00:00Z",
  detail: null,
  active_session_id: null,
});

describe("vibe-models", () => {
  it("builds ChatKit composer models with a stable default", () => {
    const models = buildVibeComposerModels([
      buildProvider("gemini", "Gemini"),
      buildProvider("codex", "Codex"),
      buildProvider("claude_code", "Claude Code"),
    ]);

    expect(models).toEqual([
      { id: "gemini", label: "Gemini", default: true },
      { id: "codex", label: "Codex" },
      { id: "claude_code", label: "Claude Code" },
    ]);
  });

  it("builds supported models for workflow ChatKit metadata", () => {
    const models = buildVibeSupportedModels([buildProvider("codex", "Codex")]);

    expect(models).toEqual([{ id: "codex", label: "Codex", default: true }]);
  });

  it("falls back to Agent when no providers are ready", () => {
    expect(getDefaultVibeProviderName([])).toBe("Agent");
    expect(buildVibeComposerModels([])).toBeUndefined();
    expect(buildVibeSupportedModels([])).toBeUndefined();
  });
});
