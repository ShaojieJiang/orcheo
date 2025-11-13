import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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

const MAX_TRACE_CACHE_ENTRIES = 20;

interface UseWorkflowTraceStateParams {
  executions: WorkflowExecution[];
}

export function useWorkflowTraceState({
  executions,
}: UseWorkflowTraceStateParams) {
  const [traces, setTraces] = useState<TraceStateMap>({});
  const traceOrderRef = useRef<string[]>([]);

  useEffect(() => {
    setTraces((prev) => {
      if (Object.keys(prev).length === 0) {
        return prev;
      }

      const allowedIds = new Set(executions.map((execution) => execution.id));
      const next: TraceStateMap = {};
      const nextOrder: string[] = [];

      traceOrderRef.current.forEach((id) => {
        if (allowedIds.has(id) && prev[id]) {
          next[id] = prev[id];
          nextOrder.push(id);
        }
      });

      traceOrderRef.current = nextOrder;
      return next;
    });
  }, [executions]);

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

  const updateTraceEntry = useCallback(
    (
      executionId: string,
      recipe: (current: TraceEntryState | undefined) => TraceEntryState,
    ) => {
      setTraces((prev) => {
        const nextEntry = recipe(prev[executionId]);
        const updated: TraceStateMap = {
          ...prev,
          [executionId]: nextEntry,
        };

        const nextOrder = traceOrderRef.current
          .filter((id) => id !== executionId)
          .concat(executionId);

        while (nextOrder.length > MAX_TRACE_CACHE_ENTRIES) {
          const removedId = nextOrder.shift();
          if (removedId) {
            delete updated[removedId];
          }
        }

        traceOrderRef.current = nextOrder;
        return updated;
      });
    },
    [],
  );

  const loadTrace = useCallback(
    async (executionId: string) => {
      updateTraceEntry(executionId, (current) => ({
        ...ensureEntry(executionId, current),
        loading: true,
        error: null,
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
        updateTraceEntry(executionId, (current) => {
          const existing = ensureEntry(executionId, current);
          return {
            entry: mergeTraceResponse(existing.entry ?? undefined, payload),
            loading: false,
            error: null,
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
        updateTraceEntry(executionId, (current) => ({
          ...ensureEntry(executionId, current),
          loading: false,
          error:
            status === 404
              ? "Trace data is not yet available. Please try again shortly."
              : message,
        }));
      }
    },
    [ensureEntry, updateTraceEntry],
  );

  const applyTraceUpdate = useCallback(
    (update: TraceUpdateMessage) => {
      const executionId = update.execution_id;
      updateTraceEntry(executionId, (current) => {
        const baseline = ensureEntry(executionId, current);
        return {
          entry: mergeTraceUpdate(baseline.entry!, update),
          loading: baseline.loading,
          error: baseline.error,
        };
      });
    },
    [ensureEntry, updateTraceEntry],
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
