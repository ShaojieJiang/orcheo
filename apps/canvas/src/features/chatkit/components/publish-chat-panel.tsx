import { ChatKit } from "@openai/chatkit-react";

import { usePublishChatKit } from "../hooks/use-publish-chatkit";

export type PublishChatPanelProps = {
  workflowId: string;
  workflowName: string;
  publishToken: string;
  onAuthError: () => void;
  onRateLimit: () => void;
};

export const PublishChatPanel = ({
  workflowId,
  workflowName,
  publishToken,
  onAuthError,
  onRateLimit,
}: PublishChatPanelProps) => {
  const { control } = usePublishChatKit({
    workflowId,
    workflowName,
    publishToken,
    onAuthError,
    onRateLimit,
  });

  return <ChatKit control={control} className="flex h-full w-full flex-col" />;
};
