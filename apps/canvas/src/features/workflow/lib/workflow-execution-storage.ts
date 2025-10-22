import type { WorkflowExecution } from "@features/workflow/components/panels/workflow-execution-history";

const STORAGE_PREFIX = "orcheo.canvas.workflow.executions";

const isBrowser = () => typeof window !== "undefined" && !!window.localStorage;

const buildStorageKey = (workflowId: string) =>
  `${STORAGE_PREFIX}:${workflowId}`;

export const loadWorkflowExecutions = (
  workflowId: string,
): WorkflowExecution[] => {
  if (!isBrowser()) {
    return [];
  }

  try {
    const key = buildStorageKey(workflowId);
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed as WorkflowExecution[];
  } catch (error) {
    console.error("Failed to load workflow executions from storage", error);
    return [];
  }
};

export const saveWorkflowExecutions = (
  workflowId: string,
  executions: WorkflowExecution[],
): void => {
  if (!isBrowser()) {
    return;
  }

  try {
    const key = buildStorageKey(workflowId);
    window.localStorage.setItem(key, JSON.stringify(executions));
  } catch (error) {
    console.error("Failed to save workflow executions to storage", error);
  }
};

export const clearWorkflowExecutions = (workflowId: string): void => {
  if (!isBrowser()) {
    return;
  }

  try {
    const key = buildStorageKey(workflowId);
    window.localStorage.removeItem(key);
  } catch (error) {
    console.error("Failed to clear workflow executions from storage", error);
  }
};
