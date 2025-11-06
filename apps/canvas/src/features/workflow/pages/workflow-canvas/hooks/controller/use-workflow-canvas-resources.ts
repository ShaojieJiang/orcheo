import { useNavigate } from "react-router-dom";
import { getBackendBaseUrl } from "@/lib/config";
import { convertPersistedEdgesToCanvas } from "@features/workflow/pages/workflow-canvas/helpers/transformers";
import { useWorkflowCredentials } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-credentials";
import { useWorkflowDuplicateNodes } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-duplicate-nodes";
import { useWorkflowClipboard } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-clipboard";
import { useWorkflowFileTransfer } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-file-transfer";
import { useWorkflowSaver } from "@features/workflow/pages/workflow-canvas/hooks/use-workflow-saver";

import type { WorkflowCanvasCore } from "./use-workflow-canvas-core";

export interface WorkflowCanvasResources {
  credentials: ReturnType<typeof useWorkflowCredentials>;
  duplicateNodes: ReturnType<typeof useWorkflowDuplicateNodes>;
  clipboard: ReturnType<typeof useWorkflowClipboard>;
  fileTransfer: ReturnType<typeof useWorkflowFileTransfer>;
  saver: ReturnType<typeof useWorkflowSaver>;
}

export function useWorkflowCanvasResources(
  core: WorkflowCanvasCore,
  workflowId: string | undefined,
): WorkflowCanvasResources {
  const navigate = useNavigate();

  const credentials = useWorkflowCredentials({
    routeWorkflowId: workflowId,
    currentWorkflowId: core.metadata.currentWorkflowId,
    backendBaseUrl: getBackendBaseUrl(),
    userName: core.user.name,
  });

  const duplicateNodes = useWorkflowDuplicateNodes({
    nodes: core.history.nodes,
    edges: core.history.edges,
    nodesRef: core.history.nodesRef,
    isRestoringRef: core.history.isRestoringRef,
    recordSnapshot: core.history.recordSnapshot,
    setNodesState: core.history.setNodesState,
    setEdgesState: core.history.setEdgesState,
    handleOpenChat: core.chat.handleOpenChat,
  });

  const clipboard = useWorkflowClipboard({
    nodesRef: core.history.nodesRef,
    edgesRef: core.history.edgesRef,
    recordSnapshot: core.history.recordSnapshot,
    setNodesState: core.history.setNodesState,
    setEdgesState: core.history.setEdgesState,
    deleteNodes: core.nodeState.deleteNodes,
    isRestoringRef: core.history.isRestoringRef,
    convertPersistedNodesToCanvas: core.convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
  });

  const fileTransfer = useWorkflowFileTransfer({
    createSnapshot: core.history.createSnapshot,
    convertPersistedNodesToCanvas: core.convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
    setNodesState: core.history.setNodesState,
    setEdgesState: core.history.setEdgesState,
    setWorkflowName: core.metadata.setWorkflowName,
    setWorkflowDescription: core.metadata.setWorkflowDescription,
    setCurrentWorkflowId: core.metadata.setCurrentWorkflowId,
    setWorkflowVersions: core.metadata.setWorkflowVersions,
    setWorkflowTags: core.metadata.setWorkflowTags,
    workflowName: core.metadata.workflowName,
    workflowDescription: core.metadata.workflowDescription,
    recordSnapshot: core.history.recordSnapshot,
    isRestoringRef: core.history.isRestoringRef,
  });

  const saver = useWorkflowSaver({
    createSnapshot: core.history.createSnapshot,
    convertPersistedNodesToCanvas: core.convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
    setWorkflowName: core.metadata.setWorkflowName,
    setWorkflowDescription: core.metadata.setWorkflowDescription,
    setCurrentWorkflowId: core.metadata.setCurrentWorkflowId,
    setWorkflowVersions: core.metadata.setWorkflowVersions,
    setWorkflowTags: core.metadata.setWorkflowTags,
    workflowName: core.metadata.workflowName,
    workflowDescription: core.metadata.workflowDescription,
    workflowTags: core.metadata.workflowTags,
    currentWorkflowId: core.metadata.currentWorkflowId,
    workflowIdFromRoute: workflowId,
    navigate,
    applySnapshot: core.history.applySnapshot,
  });

  return { credentials, duplicateNodes, clipboard, fileTransfer, saver };
}
