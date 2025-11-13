import { useCallback, useMemo, useState } from "react";

import { toast } from "@/hooks/use-toast";
import { buildBackendHttpUrl } from "@/lib/config";

import type { WorkflowExecution } from "@features/workflow/pages/workflow-canvas/helpers/types";

import {
  buildTraceViewerData,
  createFallbackTraceMetadata,
  initializeTraceStoreEntry,
  mergeTraceResponse,
  mergeTraceUpdate,
  type TraceExecutionMetadata,
  type TraceResponse,
  type TraceStoreEntry,
  type TraceUpdateMessage,
} from "@features/workflow/pages/workflow-canvas/helpers/trace";

interface TraceEntryState {
  entry: TraceStoreEntry | null;
  loading: boolean;
  error: string | null;
}

type TraceStateMap = Record<string, TraceEntryState>;

interface UseWorkflowTraceStateParams {
  executions: WorkflowExecution[];
}

export function useWorkflowTraceState({
  executions,
}: UseWorkflowTraceStateParams) {
  const [traces, setTraces] = useState<TraceStateMap>({});

  const executionMetadataLookup = useMemo(() => {
    const map = new Map<string, TraceExecutionMetadata>();
    executions.forEach((execution) => {
      map.set(
        execution.id,
        createFallbackTraceMetadata(execution.id, {
          status: execution.status,
          started_at: execution.startTime,
          finished_at: execution.endTime ?? null,
        }),
      );
    });
    return map;
  }, [executions]);

  const ensureEntry = useCallback(
    (executionId: string, current?: TraceEntryState): TraceEntryState => {
      if (current?.entry) {
        return current;
      }

      const fallbackMetadata =
        executionMetadataLookup.get(executionId) ??
        createFallbackTraceMetadata(executionId);
      return {
        entry: initializeTraceStoreEntry(fallbackMetadata),
        loading: current?.loading ?? false,
        error: current?.error ?? null,
      };
    },
    [executionMetadataLookup],
  );

  const loadTrace = useCallback(
    async (executionId: string) => {
      setTraces((prev) => ({
        ...prev,
        [executionId]: {
          ...ensureEntry(executionId, prev[executionId]),
          loading: true,
          error: null,
        },
      }));

      const url = buildBackendHttpUrl(`/api/executions/${executionId}/trace`);

      try {
        const response = await fetch(url);
        if (!response.ok) {
          const detail = await response.text();
          const error = new Error(
            detail || `Request failed with status ${response.status}`,
          ) as Error & { status?: number };
          error.status = response.status;
          throw error;
        }

        const payload = (await response.json()) as TraceResponse;
        setTraces((prev) => {
          const existing = ensureEntry(executionId, prev[executionId]);
          return {
            ...prev,
            [executionId]: {
              entry: mergeTraceResponse(existing.entry ?? undefined, payload),
              loading: false,
              error: null,
            },
          };
        });
      } catch (error) {
        const status = (error as Error & { status?: number }).status;
        const message =
          error instanceof Error
            ? error.message
            : "Failed to load execution trace.";
        if (status !== 404) {
          toast({
            title: "Trace load failed",
            description: message,
            variant: "destructive",
          });
        }
        setTraces((prev) => ({
          ...prev,
          [executionId]: {
            ...ensureEntry(executionId, prev[executionId]),
            loading: false,
            error:
              status === 404
                ? "Trace data is not yet available. Please try again shortly."
                : message,
          },
        }));
      }
    },
    [ensureEntry],
  );

  const applyTraceUpdate = useCallback(
    (update: TraceUpdateMessage) => {
      setTraces((prev) => {
        const executionId = update.execution_id;
        const baseline = ensureEntry(executionId, prev[executionId]);
        return {
          ...prev,
          [executionId]: {
            entry: mergeTraceUpdate(baseline.entry!, update),
            loading: baseline.loading,
            error: baseline.error,
          },
        };
      });
    },
    [ensureEntry],
  );

  const getViewerData = useCallback(
    (executionId: string) => {
      const entry = traces[executionId]?.entry;
      if (!entry) {
        return null;
      }
      return buildTraceViewerData(entry);
    },
    [traces],
  );

  return {
    traces,
    loadTrace,
    applyTraceUpdate,
    getViewerData,
  };
}
