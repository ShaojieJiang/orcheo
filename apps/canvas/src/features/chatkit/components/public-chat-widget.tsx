import { useMemo } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import type { UseChatKitOptions } from "@openai/chatkit-react";
import { buildBackendHttpUrl } from "@/lib/config";
import {
  buildPublicChatFetch,
  getChatKitDomainKey,
  type PublicChatHttpError,
} from "@features/chatkit/lib/chatkit-client";

interface PublicChatWidgetProps {
  workflowId: string;
  workflowName: string;
  backendBaseUrl?: string;
  onReady?: () => void;
  onHttpError?: (error: PublicChatHttpError) => void;
  onLog?: (payload: Record<string, unknown>) => void;
}

export function PublicChatWidget({
  workflowId,
  workflowName,
  backendBaseUrl,
  onReady,
  onHttpError,
  onLog,
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
        enabled: false,
      },
      composer: {
        placeholder: `Message ${workflowName}`,
      },
      startScreen: {
        greeting: `Chat with ${workflowName}.`,
      },
      onReady,
      onLog,
    };
  }, [backendBaseUrl, onHttpError, onLog, onReady, workflowId, workflowName]);

  const { control } = useChatKit(options);

  return (
    <ChatKit
      control={control}
      className="flex h-full w-full rounded-lg border border-slate-200 bg-background dark:border-slate-800"
    />
  );
}
