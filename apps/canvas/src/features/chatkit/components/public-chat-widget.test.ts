import { describe, expect, it } from "vitest";
import { buildStartScreenPrompts } from "./public-chat-config";

describe("buildStartScreenPrompts", () => {
  it("uses configured workflow prompts when present", () => {
    expect(
      buildStartScreenPrompts("Demo workflow", [
        {
          label: "Summarize the latest run",
          prompt: "Summarize the latest run for me.",
          icon: "search",
        },
        {
          label: "What changed?",
          prompt: "What changed since yesterday?",
        },
      ]),
    ).toEqual([
      {
        label: "Summarize the latest run",
        prompt: "Summarize the latest run for me.",
        icon: "search",
      },
      {
        label: "What changed?",
        prompt: "What changed since yesterday?",
      },
    ]);
  });

  it("falls back to built-in prompts when no workflow prompts are set", () => {
    expect(buildStartScreenPrompts("Demo workflow")).toEqual([
      {
        label: "What can you do?",
        prompt: "What can Demo workflow help with?",
        icon: "circle-question",
      },
      {
        label: "Introduce yourself",
        prompt: "My name is ...",
        icon: "book-open",
      },
      {
        label: "Latest results",
        prompt: "Summarize the latest run for Demo workflow.",
        icon: "search",
      },
      {
        label: "Switch theme",
        prompt: "Change the theme to dark mode",
        icon: "sparkle",
      },
    ]);
  });
});
