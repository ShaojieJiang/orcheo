import { useCallback, useRef } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import { toast } from "@/hooks/use-toast";
import {
  toPersistedEdge,
  toPersistedNode,
} from "@features/workflow/pages/workflow-canvas/helpers/transformers";
import { validateWorkflowData } from "@features/workflow/pages/workflow-canvas/helpers/validation";
import type {
  CanvasEdge,
  CanvasNode,
  WorkflowClipboardPayload,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type {
  WorkflowEdge as PersistedWorkflowEdge,
  WorkflowNode as PersistedWorkflowNode,
} from "@features/workflow/data/workflow-data";
import type { StoredWorkflow } from "@features/workflow/lib/workflow-storage";

interface WorkflowFileTransferOptions {
  createSnapshot: () => { nodes: CanvasNode[]; edges: CanvasEdge[] };
  convertPersistedNodesToCanvas: (
    nodes: PersistedWorkflowNode[],
  ) => CanvasNode[];
  convertPersistedEdgesToCanvas: (
    edges: PersistedWorkflowEdge[],
  ) => CanvasEdge[];
  setNodesState: Dispatch<SetStateAction<CanvasNode[]>>;
  setEdgesState: Dispatch<SetStateAction<CanvasEdge[]>>;
  setWorkflowName: Dispatch<SetStateAction<string>>;
  setWorkflowDescription: Dispatch<SetStateAction<string>>;
  setCurrentWorkflowId: Dispatch<SetStateAction<string | null>>;
  setWorkflowVersions: Dispatch<SetStateAction<StoredWorkflow["versions"]>>;
  setWorkflowTags: Dispatch<SetStateAction<string[]>>;
  workflowName: string;
  workflowDescription: string;
  recordSnapshot: (options?: { force?: boolean }) => void;
  isRestoringRef: MutableRefObject<boolean>;
}

interface WorkflowFileTransferHandlers {
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
  handleExportWorkflow: () => void;
  handleImportWorkflow: () => void;
  handleWorkflowFileSelected: (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => void;
}

function parseWorkflowFile(content: string): WorkflowClipboardPayload {
  const parsed = JSON.parse(content) as WorkflowClipboardPayload;
  validateWorkflowData(parsed);
  return parsed;
}

export function useWorkflowFileTransfer(
  options: WorkflowFileTransferOptions,
): WorkflowFileTransferHandlers {
  const {
    createSnapshot,
    convertPersistedNodesToCanvas,
    convertPersistedEdgesToCanvas,
    setNodesState,
    setEdgesState,
    setWorkflowName,
    setWorkflowDescription,
    setCurrentWorkflowId,
    setWorkflowVersions,
    setWorkflowTags,
    workflowName,
    workflowDescription,
    recordSnapshot,
    isRestoringRef,
  } = options;

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleExportWorkflow = useCallback(() => {
    try {
      const snapshot = createSnapshot();
      const workflowData = {
        name: workflowName,
        description: workflowDescription,
        nodes: snapshot.nodes.map(toPersistedNode),
        edges: snapshot.edges.map(toPersistedEdge),
      };
      const serialized = JSON.stringify(workflowData, null, 2);
      const blob = new Blob([serialized], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${
        workflowName.replace(/\s+/g, "-").toLowerCase() || "workflow"
      }.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast({
        title: "Workflow exported",
        description: "A JSON export has been downloaded.",
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description:
          error instanceof Error ? error.message : "Unable to export workflow.",
        variant: "destructive",
      });
    }
  }, [createSnapshot, workflowDescription, workflowName]);

  const handleImportWorkflow = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleWorkflowFileSelected = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }

      const reader = new FileReader();
      reader.onload = () => {
        try {
          const content =
            typeof reader.result === "string" ? reader.result : "";
          const parsed = parseWorkflowFile(content);

          const importedNodes = convertPersistedNodesToCanvas(parsed.nodes);
          const importedEdges = convertPersistedEdgesToCanvas(parsed.edges);

          isRestoringRef.current = true;
          recordSnapshot({ force: true });
          try {
            setNodesState(importedNodes);
            setEdgesState(importedEdges);
            if (
              typeof parsed.name === "string" &&
              parsed.name.trim().length > 0
            ) {
              setWorkflowName(parsed.name);
            }
            if (typeof parsed.description === "string") {
              setWorkflowDescription(parsed.description);
            }
            setCurrentWorkflowId(null);
            setWorkflowVersions([]);
            setWorkflowTags(["draft"]);
          } catch (error) {
            isRestoringRef.current = false;
            throw error;
          }

          toast({
            title: "Workflow imported",
            description: `Loaded ${importedNodes.length} node${
              importedNodes.length === 1 ? "" : "s"
            } from file.`,
          });
        } catch (error) {
          toast({
            title: "Import failed",
            description:
              error instanceof Error ? error.message : "Invalid workflow file.",
            variant: "destructive",
          });
        } finally {
          event.target.value = "";
        }
      };
      reader.onerror = () => {
        toast({
          title: "Import failed",
          description: "Unable to read the selected file.",
          variant: "destructive",
        });
        event.target.value = "";
      };
      reader.readAsText(file);
    },
    [
      convertPersistedEdgesToCanvas,
      convertPersistedNodesToCanvas,
      isRestoringRef,
      recordSnapshot,
      setCurrentWorkflowId,
      setEdgesState,
      setNodesState,
      setWorkflowDescription,
      setWorkflowName,
      setWorkflowTags,
      setWorkflowVersions,
    ],
  );

  return {
    fileInputRef,
    handleExportWorkflow,
    handleImportWorkflow,
    handleWorkflowFileSelected,
  };
}
