import { useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";

import { toast } from "@/hooks/use-toast";
import {
  toPersistedEdge,
  toPersistedNode,
} from "@features/workflow/pages/workflow-canvas/helpers/transformers";
import type {
  CanvasEdge,
  CanvasNode,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type {
  WorkflowEdge as PersistedWorkflowEdge,
  WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";
import {
  getVersionSnapshot,
  saveWorkflow as persistWorkflow,
  type StoredWorkflow,
} from "@features/workflow/lib/workflow-storage";

interface WorkflowSaverOptions {
  createSnapshot: () => { nodes: CanvasNode[]; edges: CanvasEdge[] };
  convertPersistedNodesToCanvas: (
    nodes: PersistedWorkflowNode[],
  ) => CanvasNode[];
  convertPersistedEdgesToCanvas: (
    edges: PersistedWorkflowEdge[],
  ) => CanvasEdge[];
  setWorkflowName: Dispatch<SetStateAction<string>>;
  setWorkflowDescription: Dispatch<SetStateAction<string>>;
  setCurrentWorkflowId: Dispatch<SetStateAction<string | null>>;
  setWorkflowVersions: Dispatch<SetStateAction<StoredWorkflow["versions"]>>;
  setWorkflowTags: Dispatch<SetStateAction<string[]>>;
  workflowName: string;
  workflowDescription: string;
  workflowTags: string[];
  currentWorkflowId: string | null;
  workflowIdFromRoute?: string;
  navigate: (path: string, options?: { replace?: boolean }) => void;
  applySnapshot: (
    snapshot: { nodes: CanvasNode[]; edges: CanvasEdge[] },
    options?: { resetHistory?: boolean },
  ) => void;
}

interface WorkflowSaverHandlers {
  handleSaveWorkflow: () => Promise<void>;
  handleTagsChange: (value: string) => void;
  handleRestoreVersion: (versionId: string) => Promise<void>;
}

export function useWorkflowSaver(
  options: WorkflowSaverOptions,
): WorkflowSaverHandlers {
  const {
    createSnapshot,
    convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
    setWorkflowName,
    setWorkflowDescription,
    setCurrentWorkflowId,
    setWorkflowVersions,
    setWorkflowTags,
    workflowName,
    workflowDescription,
    workflowTags,
    currentWorkflowId,
    workflowIdFromRoute,
    navigate,
    applySnapshot,
  } = options;

  const handleSaveWorkflow = useCallback(async () => {
    const snapshot = createSnapshot();
    const persistedNodes = snapshot.nodes.map(toPersistedNode);
    const persistedEdges = snapshot.edges.map(toPersistedEdge);
    const timestampLabel = new Date().toLocaleString();

    const tagsToPersist = workflowTags.length > 0 ? workflowTags : ["draft"];

    try {
      const saved = await persistWorkflow(
        {
          id: currentWorkflowId ?? undefined,
          name: workflowName.trim() || "Untitled Workflow",
          description: workflowDescription.trim(),
          tags: tagsToPersist,
          nodes: persistedNodes,
          edges: persistedEdges,
        },
        { versionMessage: `Manual save (${timestampLabel})` },
      );

      setCurrentWorkflowId(saved.id);
      setWorkflowName(saved.name);
      setWorkflowDescription(saved.description ?? "");
      setWorkflowTags(saved.tags ?? tagsToPersist);
      setWorkflowVersions(saved.versions ?? []);

      toast({
        title: "Workflow saved",
        description: `"${saved.name}" has been updated.`,
      });

      if (!workflowIdFromRoute || workflowIdFromRoute !== saved.id) {
        navigate(`/workflow-canvas/${saved.id}`, {
          replace: !!workflowIdFromRoute,
        });
      }
    } catch (error) {
      toast({
        title: "Failed to save workflow",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  }, [
    createSnapshot,
    currentWorkflowId,
    navigate,
    setCurrentWorkflowId,
    setWorkflowDescription,
    setWorkflowName,
    setWorkflowTags,
    setWorkflowVersions,
    workflowDescription,
    workflowIdFromRoute,
    workflowName,
    workflowTags,
  ]);

  const handleTagsChange = useCallback(
    (value: string) => {
      const tags = value
        .split(",")
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0);
      setWorkflowTags(tags);
    },
    [setWorkflowTags],
  );

  const handleRestoreVersion = useCallback(
    async (versionId: string) => {
      if (!currentWorkflowId) {
        toast({
          title: "Save required",
          description: "Save this workflow before restoring versions.",
          variant: "destructive",
        });
        return;
      }

      try {
        const snapshot = await getVersionSnapshot(currentWorkflowId, versionId);
        if (!snapshot) {
          toast({
            title: "Version unavailable",
            description: "We couldn't load that version. Please try again.",
            variant: "destructive",
          });
          return;
        }

        const canvasNodes = convertPersistedNodesToCanvas(snapshot.nodes ?? []);
        const canvasEdges = convertPersistedEdgesToCanvas(snapshot.edges ?? []);
        applySnapshot(
          { nodes: canvasNodes, edges: canvasEdges },
          { resetHistory: true },
        );
        setWorkflowName(snapshot.name);
        setWorkflowDescription(snapshot.description ?? "");
        toast({
          title: "Version loaded",
          description: "Review the restored version and save to keep it.",
        });
      } catch (error) {
        toast({
          title: "Failed to restore version",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    },
    [
      applySnapshot,
      convertPersistedEdgesToCanvas,
      convertPersistedNodesToCanvas,
      currentWorkflowId,
      setWorkflowDescription,
      setWorkflowName,
    ],
  );

  return {
    handleSaveWorkflow,
    handleTagsChange,
    handleRestoreVersion,
  };
}
