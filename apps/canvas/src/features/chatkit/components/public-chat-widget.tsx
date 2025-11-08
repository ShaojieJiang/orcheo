import { useMemo } from "react";
import type { StartScreenPrompt } from "@openai/chatkit";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import type { UseChatKitOptions } from "@openai/chatkit-react";
import { buildBackendHttpUrl } from "@/lib/config";
import { cn } from "@/lib/utils";
import {
  buildPublicChatFetch,
  getChatKitDomainKey,
  type PublicChatHttpError,
} from "@features/chatkit/lib/chatkit-client";

type ColorScheme = "light" | "dark";

interface PublicChatWidgetProps {
  workflowId: string;
  workflowName: string;
  backendBaseUrl?: string;
  onReady?: () => void;
  onHttpError?: (error: PublicChatHttpError) => void;
  onLog?: (payload: Record<string, unknown>) => void;
  colorScheme?: ColorScheme;
  onThemeRequest?: (scheme: ColorScheme) => Promise<void> | void;
}

const buildChatTheme = (
  scheme: ColorScheme,
): NonNullable<UseChatKitOptions["theme"]> => ({
  colorScheme: scheme,
  color: {
    grayscale: {
      hue: 220,
      tint: 6,
      shade: scheme === "dark" ? -1 : -4,
    },
    accent: {
      primary: scheme === "dark" ? "#f1f5f9" : "#0f172a",
      level: 1,
    },
  },
  radius: "round",
});

const buildStartScreenPrompts = (workflowName: string): StartScreenPrompt[] => [
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

const buildGreeting = (workflowName: string): string =>
  `Welcome to the ${workflowName} public chat.`;

const buildComposerPlaceholder = (workflowName: string): string =>
  `Share a fact for ${workflowName}`;

export function PublicChatWidget({
  workflowId,
  workflowName,
  backendBaseUrl,
  onReady,
  onHttpError,
  onLog,
  colorScheme = "light",
  onThemeRequest,
}: PublicChatWidgetProps) {
  const options = useMemo<UseChatKitOptions>(() => {
    const domainKey = getChatKitDomainKey();
    return {
      api: {
        url: buildBackendHttpUrl("/api/chatkit", backendBaseUrl),
        domainKey,
        fetch: buildPublicChatFetch({
          workflowId,
          backendBaseUrl,
          onHttpError,
          metadata: {
            workflow_name: workflowName,
          },
        }),
      },
      header: {
        enabled: true,
        title: { text: workflowName },
      },
      history: {
        enabled: true,
      },
      theme: buildChatTheme(colorScheme),
      startScreen: {
        greeting: buildGreeting(workflowName),
        prompts: buildStartScreenPrompts(workflowName),
      },
      composer: {
        placeholder: buildComposerPlaceholder(workflowName),
      },
      threadItemActions: {
        feedback: false,
      },
      onClientTool: async (invocation) => {
        if (invocation.name === "switch_theme") {
          const requested = invocation.params?.theme;
          if (requested === "light" || requested === "dark") {
            if (onThemeRequest) {
              await onThemeRequest(requested);
              return { success: true };
            }
            return { success: false };
          }
          return { success: false };
        }
        return { success: false };
      },
      onReady,
      onLog,
    };
  }, [
    backendBaseUrl,
    colorScheme,
    onHttpError,
    onLog,
    onReady,
    onThemeRequest,
    workflowId,
    workflowName,
  ]);

  const { control } = useChatKit(options);

  return (
    <div
      className={cn(
        "relative h-full w-full overflow-hidden rounded-3xl",
        "border border-slate-200/70 bg-white",
        "shadow-[0_25px_80px_rgba(15,23,42,0.12)]",
        "dark:border-slate-800/70 dark:bg-slate-900",
      )}
    >
      <ChatKit control={control} className="block h-full w-full" />
    </div>
  );
}
