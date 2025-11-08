import { useMemo } from "react";

import { ChatKitOptions, useChatKit } from "@openai/chatkit-react";

import {
  buildBackendHttpUrl,
  getBackendBaseUrl,
  getChatKitDomainKey,
} from "@/lib/config";

import {
  createPublishFetch,
  type PublishFetchCallbacks,
} from "../utils/create-publish-fetch";

export type UsePublishChatKitArgs = PublishFetchCallbacks & {
  workflowId: string;
  workflowName: string;
  publishToken: string;
};

export const usePublishChatKit = ({
  workflowId,
  workflowName,
  publishToken,
  onAuthError,
  onRateLimit,
}: UsePublishChatKitArgs) => {
  const backendBaseUrl = getBackendBaseUrl();

  const chatkitOptions = useMemo<ChatKitOptions>(() => {
    const apiUrl = buildBackendHttpUrl("/api/chatkit", backendBaseUrl);
    const fetchImpl = createPublishFetch({
      workflowId,
      publishToken,
      metadata: {
        workflow_id: workflowId,
        workflow_name: workflowName,
      },
      onAuthError,
      onRateLimit,
    });

    return {
      api: {
        url: apiUrl,
        domainKey: getChatKitDomainKey(),
        fetch: fetchImpl,
      },
      header: {
        enabled: true,
        title: { text: workflowName },
      },
      composer: {
        placeholder: `Ask ${workflowName}…`,
      },
      history: {
        enabled: true,
        showDelete: false,
        showRename: false,
      },
    } satisfies ChatKitOptions;
  }, [
    backendBaseUrl,
    onAuthError,
    onRateLimit,
    publishToken,
    workflowId,
    workflowName,
  ]);

  return useChatKit(chatkitOptions);
};
