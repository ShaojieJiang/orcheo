import type { Dispatch, SetStateAction } from "react";
import { useEffect } from "react";

import {
  WORKFLOW_STORAGE_EVENT,
  getWorkflowById,
} from "@features/workflow/lib/workflow-storage";
import type { StoredWorkflow } from "@features/workflow/lib/workflow-storage";

interface UseWorkflowStorageListenerParams {
  currentWorkflowId: string | null;
  setWorkflowVersions: Dispatch<SetStateAction<StoredWorkflow["versions"]>>;
  setWorkflowTags: Dispatch<SetStateAction<string[]>>;
}

export function useWorkflowStorageListener({
  currentWorkflowId,
  setWorkflowVersions,
  setWorkflowTags,
}: UseWorkflowStorageListenerParams) {
  useEffect(() => {
    if (!currentWorkflowId) {
      return;
    }

    const targetWindow = typeof window !== "undefined" ? window : undefined;
    if (!targetWindow) {
      return;
    }

    const handleStorageUpdate = async () => {
      try {
        const updated = await getWorkflowById(currentWorkflowId);
        if (updated) {
          setWorkflowVersions(updated.versions ?? []);
          setWorkflowTags(updated.tags ?? ["draft"]);
        }
      } catch (error) {
        console.error("Failed to reload workflow", error);
      }
    };

    targetWindow.addEventListener(WORKFLOW_STORAGE_EVENT, handleStorageUpdate);
    return () => {
      targetWindow.removeEventListener(
        WORKFLOW_STORAGE_EVENT,
        handleStorageUpdate,
      );
    };
  }, [currentWorkflowId, setWorkflowTags, setWorkflowVersions]);
}
