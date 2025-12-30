import { useCallback } from "react";
import type { MutableRefObject } from "react";

import { toast } from "@/hooks/use-toast";
import { getAccessToken } from "@features/auth/lib/auth-session";
import { buildWorkflowWebSocketUrl, getBackendBaseUrl } from "@/lib/config";
import { buildGraphConfigFromCanvas } from "@features/workflow/lib/graph-config";
import { generateRandomId } from "@features/workflow/pages/workflow-canvas/helpers/id";
import {
  createExecutionRecord,
  markNodesAsRunning,
} from "@features/workflow/pages/workflow-canvas/hooks/execution-record";
import { setupExecutionWebSocket } from "@features/workflow/pages/workflow-canvas/hooks/workflow-runner-websocket";

import type {
  CanvasEdge,
  CanvasNode,
  WorkflowExecution,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type { TraceUpdateMessage } from "@features/workflow/pages/workflow-canvas/helpers/trace";

interface UseRunWorkflowParams {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  setNodes: React.Dispatch<React.SetStateAction<CanvasNode[]>>;
  setExecutions: React.Dispatch<React.SetStateAction<WorkflowExecution[]>>;
  setActiveExecutionId: React.Dispatch<React.SetStateAction<string | null>>;
  setIsRunning: React.Dispatch<React.SetStateAction<boolean>>;
  websocketRef: MutableRefObject<WebSocket | null>;
  isMountedRef: MutableRefObject<boolean>;
  currentWorkflowId: string | null;
  applyExecutionUpdate: (
    executionId: string,
    payload: Record<string, unknown>,
    graphToCanvas: Record<string, string>,
  ) => void;
  handleTraceUpdate: (update: TraceUpdateMessage) => void;
}

export function useRunWorkflow({
  nodes,
  edges,
  setNodes,
  setExecutions,
  setActiveExecutionId,
  setIsRunning,
  websocketRef,
  isMountedRef,
  currentWorkflowId,
  applyExecutionUpdate,
  handleTraceUpdate,
}: UseRunWorkflowParams) {
  return useCallback(async () => {
    if (nodes.length === 0) {
      toast({
        title: "Add nodes before running",
        description: "Create at least one node to build a runnable workflow.",
        variant: "destructive",
      });
      return;
    }

    const { config, graphToCanvas, warnings } =
      await buildGraphConfigFromCanvas(nodes, edges);

    warnings.forEach((message) => {
      toast({
        title: "Workflow configuration warning",
        description: message,
      });
    });

    const executionId = generateRandomId("run");
    const executionRecord = createExecutionRecord(
      executionId,
      nodes,
      edges,
      graphToCanvas,
    );

    setExecutions((prev) => [executionRecord, ...prev]);
    setActiveExecutionId(executionId);
    setIsRunning(true);
    setNodes((prev) => markNodesAsRunning(prev));

    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }

    let websocketUrl: string;
    try {
      websocketUrl = buildWorkflowWebSocketUrl(
        currentWorkflowId ?? "canvas-preview",
        getBackendBaseUrl(),
        getAccessToken(),
      );
    } catch (error) {
      setIsRunning(false);
      toast({
        title: "Unable to start execution",
        description:
          error instanceof Error
            ? error.message
            : "Invalid workflow identifier",
        variant: "destructive",
      });
      return;
    }

    const ws = new WebSocket(websocketUrl);
    websocketRef.current = ws;

    setupExecutionWebSocket({
      ws,
      executionId,
      config,
      graphToCanvas,
      nodes,
      currentWorkflowId,
      isMountedRef,
      applyExecutionUpdate,
      setIsRunning,
      setExecutions,
      websocketRef,
      onTraceUpdate: handleTraceUpdate,
    });
  }, [
    nodes,
    edges,
    setNodes,
    setExecutions,
    setActiveExecutionId,
    setIsRunning,
    websocketRef,
    currentWorkflowId,
    applyExecutionUpdate,
    handleTraceUpdate,
    isMountedRef,
  ]);
}
