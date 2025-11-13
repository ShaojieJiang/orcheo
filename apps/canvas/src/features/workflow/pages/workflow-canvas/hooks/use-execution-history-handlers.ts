import { useCallback } from "react";

import { toast } from "@/hooks/use-toast";
import { buildBackendHttpUrl } from "@/lib/config";
import { executionStatusFromValue } from "@features/workflow/pages/workflow-canvas/helpers/execution";

import type {
  CanvasNode,
  NodeData,
  RunHistoryResponse,
  WorkflowExecution,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type { Node } from "@xyflow/react";
import type { WorkflowExecution as HistoryWorkflowExecution } from "@features/workflow/components/panels/workflow-execution-history";

interface UseExecutionHistoryHandlersParams {
  setNodes: React.Dispatch<React.SetStateAction<CanvasNode[]>>;
  setExecutions: React.Dispatch<React.SetStateAction<WorkflowExecution[]>>;
  setActiveExecutionId: React.Dispatch<React.SetStateAction<string | null>>;
  activeExecutionId: string | null;
  executions: WorkflowExecution[];
  determineLogLevel: (
    payload: Record<string, unknown>,
  ) => "INFO" | "DEBUG" | "ERROR" | "WARNING";
  describePayload: (
    payload: Record<string, unknown>,
    graphToCanvas: Record<string, string>,
  ) => string;
  setActiveTab: (value: string) => void;
}

export function useExecutionHistoryHandlers({
  setNodes,
  setExecutions,
  setActiveExecutionId,
  activeExecutionId,
  executions,
  determineLogLevel,
  describePayload,
  setActiveTab,
}: UseExecutionHistoryHandlersParams) {
  const handleViewExecutionDetails = useCallback(
    (execution: HistoryWorkflowExecution) => {
      const mappedNodes = execution.nodes.map(
        (node) =>
          ({
            id: node.id,
            type: node.type || "default",
            position: node.position,
            data: {
              type: node.type || "default",
              label: node.name,
              status: node.status || ("idle" as const),
              details: node.details,
            } as NodeData,
            draggable: true,
          }) as Node<NodeData>,
      );
      setNodes(mappedNodes);
      setActiveExecutionId(execution.id);
      setActiveTab("trace");
    },
    [setActiveExecutionId, setActiveTab, setNodes],
  );

  const handleCopyExecutionToEditor = useCallback(
    (execution: HistoryWorkflowExecution) => {
      handleViewExecutionDetails(execution);
      toast({
        title: "Execution copied to canvas",
        description: `Run ${execution.runId} was loaded into the editor.`,
      });
    },
    [handleViewExecutionDetails],
  );

  const handleDeleteExecution = useCallback(
    (execution: HistoryWorkflowExecution) => {
      setExecutions((prev) => prev.filter((item) => item.id !== execution.id));
      if (activeExecutionId === execution.id) {
        setActiveExecutionId(null);
      }
      toast({
        title: "Execution removed",
        description: `Run ${execution.runId} was removed from the history view.`,
      });
    },
    [activeExecutionId, setActiveExecutionId, setExecutions],
  );

  const handleRefreshExecutionHistory = useCallback(async () => {
    if (typeof fetch === "undefined") {
      toast({
        title: "Refresh unavailable",
        description: "The Fetch API is not available in this environment.",
        variant: "destructive",
      });
      return;
    }

    const targetExecution =
      (activeExecutionId &&
        executions.find((execution) => execution.id === activeExecutionId)) ||
      executions[0];

    if (!targetExecution) {
      toast({
        title: "No executions to refresh",
        description: "Run a workflow to create live execution history.",
      });
      return;
    }

    const url = buildBackendHttpUrl(
      `/api/executions/${targetExecution.id}/history`,
    );

    try {
      const response = await fetch(url);
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(
          detail || `Request failed with status ${response.status}`,
        );
      }

      const history = (await response.json()) as RunHistoryResponse;
      const mapping = targetExecution.metadata?.graphToCanvas ?? {};

      const logs = history.steps.map((step) => ({
        timestamp: new Date(step.at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        level: determineLogLevel(step.payload),
        message: describePayload(step.payload, mapping),
      }));

      setExecutions((prev) =>
        prev.map((execution) => {
          if (execution.id !== history.execution_id) {
            return execution;
          }
          const status =
            executionStatusFromValue(history.status) ?? execution.status;
          const completedAt = history.completed_at ?? execution.endTime;
          return {
            ...execution,
            status,
            logs,
            endTime: completedAt ?? undefined,
            duration: completedAt
              ? new Date(completedAt).getTime() -
                new Date(history.started_at).getTime()
              : execution.duration,
          };
        }),
      );

      toast({
        title: "Execution history refreshed",
        description: `Loaded ${history.steps.length} streamed updates.`,
      });
    } catch (error) {
      toast({
        title: "Failed to refresh execution history",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  }, [
    activeExecutionId,
    describePayload,
    determineLogLevel,
    executions,
    setExecutions,
  ]);

  return {
    handleViewExecutionDetails,
    handleCopyExecutionToEditor,
    handleDeleteExecution,
    handleRefreshExecutionHistory,
  };
}
