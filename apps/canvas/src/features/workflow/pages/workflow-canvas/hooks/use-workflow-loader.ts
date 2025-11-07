import type { Dispatch, SetStateAction } from "react";
import { useEffect } from "react";

import { toast } from "@/hooks/use-toast";
import {
  SAMPLE_WORKFLOWS,
  type WorkflowNode as PersistedWorkflowNode,
  type WorkflowEdge as PersistedWorkflowEdge,
} from "@features/workflow/data/workflow-data";
import {
  getWorkflowById,
  type StoredWorkflow,
} from "@features/workflow/lib/workflow-storage";
import { loadWorkflowExecutions } from "@features/workflow/lib/workflow-execution-storage";
import type { WorkflowExecution } from "@features/workflow/pages/workflow-canvas/helpers/types";

interface UseWorkflowLoaderParams<TNode, TEdge> {
  workflowId: string | undefined;
  setCurrentWorkflowId: Dispatch<SetStateAction<string | null>>;
  setWorkflowName: Dispatch<SetStateAction<string>>;
  setWorkflowDescription: Dispatch<SetStateAction<string>>;
  setWorkflowTags: Dispatch<SetStateAction<string[]>>;
  setWorkflowVersions: Dispatch<SetStateAction<StoredWorkflow["versions"]>>;
  setExecutions: Dispatch<SetStateAction<WorkflowExecution[]>>;
  convertPersistedNodesToCanvas: (nodes: PersistedWorkflowNode[]) => TNode[];
  convertPersistedEdgesToCanvas: (edges: PersistedWorkflowEdge[]) => TEdge[];
  applySnapshot: (
    snapshot: { nodes: TNode[]; edges: TEdge[] },
    options?: { resetHistory?: boolean },
  ) => void;
}

export function useWorkflowLoader<TNode, TEdge>({
  workflowId,
  setCurrentWorkflowId,
  setWorkflowName,
  setWorkflowDescription,
  setWorkflowTags,
  setWorkflowVersions,
  setExecutions,
  convertPersistedNodesToCanvas,
  convertPersistedEdgesToCanvas,
  applySnapshot,
}: UseWorkflowLoaderParams<TNode, TEdge>) {
  useEffect(() => {
    let isMounted = true;

    const resetToBlankWorkflow = () => {
      setCurrentWorkflowId(null);
      setWorkflowName("New Workflow");
      setWorkflowDescription("");
      setWorkflowTags(["draft"]);
      setWorkflowVersions([]);
      setExecutions([]);
      applySnapshot({ nodes: [], edges: [] }, { resetHistory: true });
    };

    const loadWorkflow = async () => {
      if (!workflowId) {
        return;
      }

      try {
        const persisted = await getWorkflowById(workflowId);
        if (persisted && isMounted) {
          setCurrentWorkflowId(persisted.id);
          setWorkflowName(persisted.name);
          setWorkflowDescription(persisted.description ?? "");
          setWorkflowTags(persisted.tags ?? ["draft"]);
          setWorkflowVersions(persisted.versions ?? []);
          const canvasNodes = convertPersistedNodesToCanvas(
            persisted.nodes ?? [],
          );
          const canvasEdges = convertPersistedEdgesToCanvas(
            persisted.edges ?? [],
          );
          applySnapshot(
            { nodes: canvasNodes, edges: canvasEdges },
            { resetHistory: true },
          );
          try {
            const history = await loadWorkflowExecutions(workflowId, {
              workflow: persisted,
            });
            if (isMounted) {
              setExecutions(history);
            }
          } catch (historyError) {
            if (isMounted) {
              setExecutions([]);
              toast({
                title: "Failed to load execution history",
                description:
                  historyError instanceof Error
                    ? historyError.message
                    : "Unable to retrieve workflow runs.",
                variant: "destructive",
              });
            }
            console.error("Failed to load workflow executions", historyError);
          }
          return;
        }
      } catch (error) {
        if (isMounted) {
          toast({
            title: "Failed to load workflow",
            description:
              error instanceof Error ? error.message : "Unknown error occurred",
            variant: "destructive",
          });
          setExecutions([]);
        }
      }

      if (!isMounted) {
        return;
      }

      const template = SAMPLE_WORKFLOWS.find((w) => w.id === workflowId);
      if (template) {
        setCurrentWorkflowId(null);
        setWorkflowName(template.name);
        setWorkflowDescription(template.description ?? "");
        setWorkflowTags(template.tags.filter((tag) => tag !== "template"));
        setWorkflowVersions([]);
        setExecutions([]);
        const canvasNodes = convertPersistedNodesToCanvas(template.nodes);
        const canvasEdges = convertPersistedEdgesToCanvas(template.edges);
        applySnapshot(
          { nodes: canvasNodes, edges: canvasEdges },
          { resetHistory: true },
        );
        toast({
          title: "Template loaded",
          description: "Save to add this workflow to your workspace.",
        });
        return;
      }

      toast({
        title: "Workflow not found",
        description: "Starting a new workflow instead.",
        variant: "destructive",
      });
      resetToBlankWorkflow();
    };

    void loadWorkflow();

    return () => {
      isMounted = false;
    };
  }, [
    applySnapshot,
    convertPersistedEdgesToCanvas,
    convertPersistedNodesToCanvas,
    setCurrentWorkflowId,
    setExecutions,
    setWorkflowDescription,
    setWorkflowName,
    setWorkflowTags,
    setWorkflowVersions,
    workflowId,
  ]);
}
