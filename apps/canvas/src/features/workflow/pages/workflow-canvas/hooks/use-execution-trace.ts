import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MutableRefObject } from "react";

import { toast } from "@/hooks/use-toast";
import { buildBackendHttpUrl } from "@/lib/config";
import type { TraceViewerData } from "@features/workflow/components/trace/agent-prism";
import {
  applyTraceResponse,
  applyTraceUpdate,
  buildTraceViewerData,
  createEmptyTraceEntry,
  deriveViewerDataList,
  ExecutionTraceEntry,
  ExecutionTraceState,
  getEntryError,
  getEntryStatus,
  markTraceLoading,
  summarizeTrace,
  TraceEntryStatus,
  type TraceResponse,
  type TraceUpdateMessage,
} from "@features/workflow/pages/workflow-canvas/helpers/trace";

export interface UseExecutionTraceParams {
  backendBaseUrl: string;
  activeExecutionId: string | null;
  isMountedRef: MutableRefObject<boolean>;
  executionIds?: string[];
}

export interface ExecutionTraceResult {
  traces: ExecutionTraceState;
  activeTrace?: ExecutionTraceEntry;
  activeTraceViewer?: TraceViewerData;
  viewerData: TraceViewerData[];
  status: TraceEntryStatus;
  error?: string;
  refresh: (executionId?: string) => Promise<void>;
  handleTraceUpdate: (update: TraceUpdateMessage) => void;
}

const buildTraceUrl = (backendBaseUrl: string, executionId: string): string =>
  buildBackendHttpUrl(`/api/executions/${executionId}/trace`, backendBaseUrl);

const buildArtifactResolver =
  (backendBaseUrl: string) => (artifactId: string) =>
    buildBackendHttpUrl(
      `/api/artifacts/${encodeURIComponent(artifactId)}/download`,
      backendBaseUrl,
    );

export function useExecutionTrace({
  backendBaseUrl,
  activeExecutionId,
  isMountedRef,
  executionIds,
}: UseExecutionTraceParams): ExecutionTraceResult {
  const [traces, setTraces] = useState<ExecutionTraceState>({});
  const fetchingRef = useRef(new Set<string>());
  const primedExecutionsRef = useRef(new Set<string>());

  const resolveArtifactUrl = useMemo(
    () => buildArtifactResolver(backendBaseUrl),
    [backendBaseUrl],
  );

  const refresh = useCallback(
    async (targetExecutionId?: string) => {
      const executionId = targetExecutionId ?? activeExecutionId;
      if (!executionId) {
        return;
      }
      if (fetchingRef.current.has(executionId)) {
        return;
      }
      fetchingRef.current.add(executionId);
      setTraces((prev) => ({
        ...prev,
        [executionId]: markTraceLoading(
          prev[executionId] ?? createEmptyTraceEntry(executionId),
        ),
      }));
      try {
        const response = await fetch(
          buildTraceUrl(backendBaseUrl, executionId),
        );
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(
            detail || `Failed to load trace for execution ${executionId}`,
          );
        }
        const payload = (await response.json()) as TraceResponse;
        if (!isMountedRef.current) {
          return;
        }
        setTraces((prev) => {
          const current =
            prev[executionId] ?? createEmptyTraceEntry(executionId);
          const next = applyTraceResponse(current, payload);
          return {
            ...prev,
            [executionId]: next,
          };
        });
      } catch (error) {
        if (!isMountedRef.current) {
          return;
        }
        const message =
          error instanceof Error ? error.message : "Failed to load trace";
        toast({
          title: "Trace fetch failed",
          description: message,
          variant: "destructive",
        });
        setTraces((prev) => {
          const current =
            prev[executionId] ?? createEmptyTraceEntry(executionId);
          return {
            ...prev,
            [executionId]: {
              ...current,
              status: "error",
              error: message,
            },
          };
        });
      } finally {
        fetchingRef.current.delete(executionId);
      }
    },
    [activeExecutionId, backendBaseUrl, isMountedRef],
  );

  const handleTraceUpdate = useCallback((update: TraceUpdateMessage) => {
    setTraces((prev) => {
      const current =
        prev[update.execution_id] ?? createEmptyTraceEntry(update.execution_id);
      const next = applyTraceUpdate(current, update);
      return {
        ...prev,
        [update.execution_id]: next,
      };
    });
  }, []);

  useEffect(() => {
    if (!executionIds?.length) {
      return;
    }
    setTraces((prev) => {
      let next: ExecutionTraceState | undefined;
      for (const executionId of executionIds) {
        if (prev[executionId]) {
          continue;
        }
        if (!next) {
          next = { ...prev };
        }
        next[executionId] = createEmptyTraceEntry(executionId);
      }
      return next ?? prev;
    });
    for (const executionId of executionIds) {
      if (primedExecutionsRef.current.has(executionId)) {
        continue;
      }
      primedExecutionsRef.current.add(executionId);
      void refresh(executionId);
    }
  }, [executionIds, refresh]);

  useEffect(() => {
    if (!activeExecutionId) {
      return;
    }
    const entry = traces[activeExecutionId];
    if (!entry || entry.status === "idle" || entry.status === "error") {
      void refresh(activeExecutionId);
    }
  }, [activeExecutionId, refresh, traces]);

  const activeTrace = activeExecutionId ? traces[activeExecutionId] : undefined;

  const activeTraceViewer = useMemo(() => {
    if (!activeTrace) {
      return undefined;
    }
    return buildTraceViewerData(activeTrace, {
      resolveArtifactUrl,
    });
  }, [activeTrace, resolveArtifactUrl]);

  const viewerData = useMemo(
    () => deriveViewerDataList(traces, { resolveArtifactUrl }),
    [traces, resolveArtifactUrl],
  );

  const status = getEntryStatus(activeTrace);
  const error = getEntryError(activeTrace);

  useEffect(() => {
    if (!activeTrace) {
      return;
    }
    if (activeTrace.status === "ready" && !activeTrace.isComplete) {
      const summary = summarizeTrace(activeTrace);
      if (summary.spanCount === 0 && !fetchingRef.current.size) {
        void refresh(activeTrace.executionId);
      }
    }
  }, [activeTrace, refresh]);

  return {
    traces,
    activeTrace,
    activeTraceViewer,
    viewerData,
    status,
    error,
    refresh,
    handleTraceUpdate,
  };
}
