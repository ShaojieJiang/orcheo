import { useCallback } from "react";
import type { MutableRefObject } from "react";

import { toast } from "@/hooks/use-toast";

import type {
  CanvasNode,
  NodeStatus,
  WorkflowExecution,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

interface UsePauseWorkflowParams {
  activeExecutionId: string | null;
  isRunning: boolean;
  setIsRunning: React.Dispatch<React.SetStateAction<boolean>>;
  setNodes: React.Dispatch<React.SetStateAction<CanvasNode[]>>;
  setExecutions: React.Dispatch<React.SetStateAction<WorkflowExecution[]>>;
  websocketRef: MutableRefObject<WebSocket | null>;
}

export function usePauseWorkflow({
  activeExecutionId,
  isRunning,
  setIsRunning,
  setNodes,
  setExecutions,
  websocketRef,
}: UsePauseWorkflowParams) {
  return useCallback(() => {
    if (!isRunning) {
      return;
    }

    setIsRunning(false);
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }

    const timestamp = new Date();

    setNodes((nds) =>
      nds.map((node) => {
        if (node.data.status === "running") {
          return {
            ...node,
            data: { ...node.data, status: "warning" as NodeStatus },
          };
        }
        return node;
      }),
    );

    if (activeExecutionId) {
      setExecutions((prev) =>
        prev.map((execution) => {
          if (execution.id !== activeExecutionId) {
            return execution;
          }
          return {
            ...execution,
            status: "partial",
            endTime: timestamp.toISOString(),
            duration:
              timestamp.getTime() - new Date(execution.startTime).getTime(),
            logs: [
              ...execution.logs,
              {
                timestamp: timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                }),
                level: "WARNING" as const,
                message: "Execution paused from the canvas",
              },
            ],
          };
        }),
      );
    }

    toast({
      title: "Workflow paused",
      description: "Live updates disconnected. Resume to reconnect.",
    });
  }, [
    activeExecutionId,
    isRunning,
    setExecutions,
    setIsRunning,
    setNodes,
    websocketRef,
  ]);
}
