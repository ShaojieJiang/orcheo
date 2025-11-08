import { useMemo } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import type { UseChatKitOptions } from "@openai/chatkit-react";
import { buildBackendHttpUrl } from "@/lib/config";
import {
  buildPublishFetch,
  getChatKitDomainKey,
  type PublishHttpError,
} from "@features/chatkit/lib/chatkit-client";

interface PublicChatWidgetProps {
  workflowId: string;
  workflowName: string;
  publishToken: string;
  backendBaseUrl?: string;
  onReady?: () => void;
  onHttpError?: (error: PublishHttpError) => void;
  onLog?: (payload: Record<string, unknown>) => void;
}

export function PublicChatWidget({
  workflowId,
  workflowName,
  publishToken,
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
        fetch: buildPublishFetch({
          workflowId,
          publishToken,
          backendBaseUrl,
          onHttpError,
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
  }, [
    backendBaseUrl,
    onHttpError,
    onLog,
    onReady,
    publishToken,
    workflowId,
    workflowName,
  ]);

  const { control } = useChatKit(options);

  return (
    <ChatKit
      control={control}
      className="flex h-full w-full rounded-lg border border-slate-800 bg-background"
    />
  );
}
