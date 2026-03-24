import type { StartScreenPrompt } from "@openai/chatkit";
import type { ChatKitStartScreenPrompt as WorkflowChatKitStartScreenPrompt } from "@features/workflow/lib/workflow-storage.types";

export const buildStartScreenPrompts = (
  workflowName: string,
  configuredPrompts?: WorkflowChatKitStartScreenPrompt[] | null,
): StartScreenPrompt[] => {
  if (configuredPrompts !== undefined && configuredPrompts !== null) {
    return configuredPrompts.map((prompt) => ({
      label: prompt.label,
      prompt: prompt.prompt,
      ...(prompt.icon ? { icon: prompt.icon } : {}),
    }));
  }

  return [
    {
      label: "What can you do?",
      prompt: `What can ${workflowName} help with?`,
      icon: "circle-question",
    },
    {
      label: "Introduce yourself",
      prompt: "My name is ...",
      icon: "book-open",
    },
    {
      label: "Latest results",
      prompt: `Summarize the latest run for ${workflowName}.`,
      icon: "search",
    },
    {
      label: "Switch theme",
      prompt: "Change the theme to dark mode",
      icon: "sparkle",
    },
  ];
};
