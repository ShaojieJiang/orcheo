import { useCallback } from "react";
import type { MutableRefObject } from "react";

import {
  determineLogLevel as determineLogLevelRaw,
  describePayload as describePayloadRaw,
} from "@features/workflow/pages/workflow-canvas/hooks/execution-log-helpers";
import {
  deriveNodeStatusUpdates,
  nextExecutionStatus,
} from "@features/workflow/pages/workflow-canvas/hooks/execution-node-status";
import { collectRuntimeUpdates } from "@features/workflow/pages/workflow-canvas/hooks/execution-runtime-updates";
import { updateExecutionRecord } from "@features/workflow/pages/workflow-canvas/hooks/execution-record-updater";
import { updateCanvasNodes } from "@features/workflow/pages/workflow-canvas/hooks/execution-canvas-updater";

import type {
  CanvasNode,
  WorkflowExecution,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

interface UseExecutionUpdatesParams {
  resolveNodeLabel: (nodeId: string) => string;
  setExecutions: React.Dispatch<React.SetStateAction<WorkflowExecution[]>>;
  setNodes: React.Dispatch<React.SetStateAction<CanvasNode[]>>;
  setIsRunning: React.Dispatch<React.SetStateAction<boolean>>;
  websocketRef: MutableRefObject<WebSocket | null>;
  isMountedRef: MutableRefObject<boolean>;
}

interface ExecutionUpdateHandlers {
  determineLogLevel: (
    payload: Record<string, unknown>,
  ) => "INFO" | "DEBUG" | "ERROR" | "WARNING";
  describePayload: (
    payload: Record<string, unknown>,
    graphToCanvas: Record<string, string>,
  ) => string;
  applyExecutionUpdate: (
    executionId: string,
    payload: Record<string, unknown>,
    graphToCanvas: Record<string, string>,
  ) => void;
}

export function useExecutionUpdates({
  resolveNodeLabel,
  setExecutions,
  setNodes,
  setIsRunning,
  websocketRef,
  isMountedRef,
}: UseExecutionUpdatesParams): ExecutionUpdateHandlers {
  const determineLogLevel = useCallback(
    (payload: Record<string, unknown>) => determineLogLevelRaw(payload),
    [],
  );

  const describePayload = useCallback(
    (payload: Record<string, unknown>, graphToCanvas: Record<string, string>) =>
      describePayloadRaw(payload, graphToCanvas, resolveNodeLabel),
    [resolveNodeLabel],
  );

  const applyExecutionUpdate = useCallback(
    (
      executionId: string,
      payload: Record<string, unknown>,
      graphToCanvas: Record<string, string>,
    ) => {
      if (!isMountedRef.current) {
        return;
      }

      const hasNodeReference = ["node", "step", "name"].some(
        (key) => typeof payload[key] === "string" && payload[key],
      );
      const executionStatus = nextExecutionStatus(payload, hasNodeReference);

      const nodeUpdates = deriveNodeStatusUpdates(payload, graphToCanvas);
      const timestamp = new Date();
      const updatedAt = timestamp.toISOString();
      const runtimeUpdates = collectRuntimeUpdates(
        payload,
        graphToCanvas,
        updatedAt,
      );

      const logLevel = determineLogLevel(payload);
      const message = describePayload(payload, graphToCanvas);

      setExecutions((prev) =>
        prev.map((execution) => {
          if (execution.id !== executionId) {
            return execution;
          }

          return updateExecutionRecord({
            execution,
            executionStatus,
            nodeUpdates,
            runtimeUpdates,
            logLevel,
            message,
            timestamp,
            graphToCanvas,
          });
        }),
      );

      setNodes((prev) =>
        updateCanvasNodes({
          nodes: prev,
          nodeUpdates,
          runtimeUpdates,
          executionStatus,
        }),
      );

      if (executionStatus && executionStatus !== "running") {
        setIsRunning(false);
        if (websocketRef.current) {
          websocketRef.current.close();
          websocketRef.current = null;
        }
      }
    },
    [
      describePayload,
      determineLogLevel,
      isMountedRef,
      setExecutions,
      setIsRunning,
      setNodes,
      websocketRef,
    ],
  );

  return {
    determineLogLevel,
    describePayload,
    applyExecutionUpdate,
  };
}
