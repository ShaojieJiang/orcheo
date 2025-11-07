import { useCallback, useState } from "react";

import { buildBackendHttpUrl } from "@/lib/config";
import type {
  CanvasNode,
  NodeData,
  NodeStatus,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

type UseWorkflowChatArgs = {
  nodesRef: React.MutableRefObject<CanvasNode[]>;
  setNodes: React.Dispatch<React.SetStateAction<CanvasNode[]>>;
  workflowId: string | null | undefined;
  backendBaseUrl: string | null;
  userName: string;
};

export const useWorkflowChat = ({
  nodesRef,
  setNodes,
  workflowId,
  backendBaseUrl,
  userName,
}: UseWorkflowChatArgs) => {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeChatNodeId, setActiveChatNodeId] = useState<string | null>(null);
  const [chatTitle, setChatTitle] = useState("Chat");

  const handleOpenChat = useCallback(
    (nodeId: string) => {
      const chatNode = nodesRef.current.find((node) => node.id === nodeId);
      if (chatNode) {
        setChatTitle(chatNode.data.label || "Chat");
        setActiveChatNodeId(nodeId);
        setIsChatOpen(true);
      }
    },
    [nodesRef],
  );

  const handleChatResponseStart = useCallback(() => {
    if (!activeChatNodeId) {
      return;
    }

    setNodes((nodes) =>
      nodes.map((node) =>
        node.id === activeChatNodeId
          ? {
              ...node,
              data: {
                ...node.data,
                status: "running" as NodeStatus,
              },
            }
          : node,
      ),
    );
  }, [activeChatNodeId, setNodes]);

  const handleChatResponseEnd = useCallback(() => {
    if (!activeChatNodeId) {
      return;
    }

    setNodes((nodes) =>
      nodes.map((node) =>
        node.id === activeChatNodeId
          ? {
              ...node,
              data: {
                ...node.data,
                status: "success" as NodeStatus,
              },
            }
          : node,
      ),
    );
  }, [activeChatNodeId, setNodes]);

  const handleChatClientTool = useCallback(
    async (toolCall: { name: string; params: Record<string, unknown> }) => {
      if (!activeChatNodeId || toolCall.name !== "orcheo.run_workflow") {
        return {};
      }

      if (!workflowId) {
        throw new Error("Cannot trigger workflow without a workflow ID");
      }

      const params = toolCall.params ?? {};
      const rawMessage =
        typeof params.message === "string" ? params.message : "";
      const threadId =
        typeof params.threadId === "string"
          ? params.threadId
          : typeof params.thread_id === "string"
            ? params.thread_id
            : null;

      const metadata = { ...(params as Record<string, unknown>) };
      delete metadata.message;
      delete metadata.threadId;
      delete metadata.thread_id;

      const response = await fetch(
        buildBackendHttpUrl(
          `/api/chatkit/workflows/${workflowId}/trigger`,
          backendBaseUrl,
        ),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: rawMessage,
            actor: userName,
            client_thread_id: threadId,
            metadata,
          }),
        },
      );

      if (!response.ok) {
        throw new Error("Failed to trigger workflow via ChatKit client tool");
      }

      const result = (await response.json()) as Record<string, unknown>;

      return result;
    },
    [activeChatNodeId, backendBaseUrl, userName, workflowId],
  );

  const attachChatHandlerToNode = useCallback(
    (node: CanvasNode): CanvasNode => {
      if (node.type !== "chatTrigger") {
        return node;
      }
      const data = node.data as NodeData;
      return {
        ...node,
        data: {
          ...data,
          onOpenChat: () => handleOpenChat(node.id),
        },
      };
    },
    [handleOpenChat],
  );

  return {
    isChatOpen,
    setIsChatOpen,
    activeChatNodeId,
    setActiveChatNodeId,
    chatTitle,
    setChatTitle,
    handleOpenChat,
    handleChatResponseStart,
    handleChatResponseEnd,
    handleChatClientTool,
    attachChatHandlerToNode,
  };
};
