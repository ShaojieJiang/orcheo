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
    setCurrentWorkflowId: core.metadata.setCurrentWorkflowId,
    setWorkflowName: core.metadata.setWorkflowName,
    setWorkflowDescription: core.metadata.setWorkflowDescription,
    setWorkflowTags: core.metadata.setWorkflowTags,
    setWorkflowVersions: core.metadata.setWorkflowVersions,
    setExecutions: core.execution.setExecutions,
    setActiveExecutionId: core.execution.setActiveExecutionId,
    convertPersistedNodesToCanvas: core.convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
    applySnapshot: core.history.applySnapshot,
  });

  useWorkflowStorageListener({
    currentWorkflowId: core.metadata.currentWorkflowId,
    setWorkflowVersions: core.metadata.setWorkflowVersions,
    setWorkflowTags: core.metadata.setWorkflowTags,
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
