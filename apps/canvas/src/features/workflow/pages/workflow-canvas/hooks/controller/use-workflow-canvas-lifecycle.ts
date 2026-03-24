import { useEffect } from "react";

import { convertPersistedEdgesToCanvas } from "@features/workflow/pages/workflow-canvas/helpers/transformers";
import { useWorkflowLoader } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-loader";
import { useWorkflowStorageListener } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-storage-listener";
import { useInitialFitView } from "@features/workflow/pages/workflow-canvas/hooks/use-initial-fit-view";

import type { WorkflowCanvasCore } from "./use-workflow-canvas-core";

export function useWorkflowCanvasLifecycle(
  core: WorkflowCanvasCore,
  workflowId: string | undefined,
) {
  useWorkflowLoader({
    workflowId,
    loadExecutionHistory: core.ui.activeTab === "trace",
    setCurrentWorkflowId: core.metadata.setCurrentWorkflowId,
    setWorkflowName: core.metadata.setWorkflowName,
    setWorkflowDescription: core.metadata.setWorkflowDescription,
    setWorkflowTags: core.metadata.setWorkflowTags,
    setWorkflowVersions: core.metadata.setWorkflowVersions,
    setChatkitStartScreenPrompts: core.metadata.setChatkitStartScreenPrompts,
    setChatkitSupportedModels: core.metadata.setChatkitSupportedModels,
    setIsWorkflowPublic: core.metadata.setIsWorkflowPublic,
    setWorkflowShareUrl: core.metadata.setWorkflowShareUrl,
    setIsWorkflowLoading: core.metadata.setIsWorkflowLoading,
    setWorkflowLoadError: core.metadata.setWorkflowLoadError,
    setExecutions: core.execution.setExecutions,
    setActiveExecutionId: core.execution.setActiveExecutionId,
    convertPersistedNodesToCanvas: core.convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
    applySnapshot: core.history.applySnapshot,
  });

  useWorkflowStorageListener({
    currentWorkflowId: core.metadata.currentWorkflowId,
    setWorkflowName: core.metadata.setWorkflowName,
    setWorkflowDescription: core.metadata.setWorkflowDescription,
    setWorkflowVersions: core.metadata.setWorkflowVersions,
    setWorkflowTags: core.metadata.setWorkflowTags,
    setChatkitStartScreenPrompts: core.metadata.setChatkitStartScreenPrompts,
    setChatkitSupportedModels: core.metadata.setChatkitSupportedModels,
  });

  useInitialFitView(core.reactFlowInstance);

  useEffect(() => {
    if (
      core.ui.hoveredEdgeId &&
      !core.history.edges.some((edge) => edge.id === core.ui.hoveredEdgeId)
    ) {
      core.ui.setHoveredEdgeId(null);
    }
  }, [core.history.edges, core.ui]);
}
