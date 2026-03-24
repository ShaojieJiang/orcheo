import { useMemo } from "react";
import type { UseChatKitOptions } from "@openai/chatkit-react";
import { buildBackendHttpUrl } from "@/lib/config";
import { cn } from "@/lib/utils";
import type { ColorScheme } from "@/hooks/use-color-scheme";
import type { ChatKitStartScreenPrompt as WorkflowChatKitStartScreenPrompt } from "@features/workflow/lib/workflow-storage.types";
import {
  buildPublicChatFetch,
  getChatKitDomainKey,
  type PublicChatHttpError,
} from "@features/chatkit/lib/chatkit-client";
import { ChatKitSurface } from "@features/chatkit/components/chatkit-surface";
import { buildChatTheme } from "@features/chatkit/lib/chatkit-theme";
import { buildStartScreenPrompts } from "@features/chatkit/components/public-chat-config";

interface PublicChatWidgetProps {
  workflowId: string;
  workflowName: string;
  backendBaseUrl?: string;
  onReady?: () => void;
  onHttpError?: (error: PublicChatHttpError) => void;
  onLog?: (payload: Record<string, unknown>) => void;
  colorScheme?: ColorScheme;
  onThemeRequest?: (scheme: ColorScheme) => Promise<void> | void;
  startScreenPrompts?: WorkflowChatKitStartScreenPrompt[] | null;
}

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
  startScreenPrompts,
}: PublicChatWidgetProps) {
  const options = useMemo<UseChatKitOptions>(() => {
    const domainKey = getChatKitDomainKey();
    const uploadUrl = buildBackendHttpUrl(
      "/api/chatkit/upload",
      backendBaseUrl,
    );

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
        uploadStrategy: { type: "direct", uploadUrl },
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
        prompts: buildStartScreenPrompts(workflowName, startScreenPrompts),
      },
      composer: {
        placeholder: buildComposerPlaceholder(workflowName),
        models: [
          {
            id: "gpt-5",
            label: "gpt-5",
            description: "Balanced intelligence",
            default: true,
          },
        ],
        tools: [
          {
            id: "search_docs",
            label: "Search docs",
            shortLabel: "Docs",
            placeholderOverride: "Search documentation",
            icon: "book-open",
            pinned: false,
          },
        ],
        attachments: {
          enabled: true,
          accept: {
            "text/plain": [".txt"],
            "text/markdown": [".md"],
            "application/json": [".json"],
            "text/csv": [".csv"],
            "text/x-log": [".log"],
          },
          maxSize: 5 * 1024 * 1024, // 5MB
          maxCount: 10,
        },
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
    startScreenPrompts,
    workflowId,
    workflowName,
  ]);

  return (
    <div
      className={cn(
        "relative h-full w-full overflow-hidden rounded-3xl",
        "border border-slate-200/70 bg-white",
        "shadow-[0_25px_80px_rgba(15,23,42,0.12)]",
        "dark:border-slate-800/70 dark:bg-slate-900",
      )}
    >
      <ChatKitSurface options={options} />
    </div>
  );
}
