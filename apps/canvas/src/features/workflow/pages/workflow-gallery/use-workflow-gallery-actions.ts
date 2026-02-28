import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";
import { type Workflow } from "@features/workflow/data/workflow-data";
import {
  createWorkflow,
  createWorkflowFromTemplate,
  deleteWorkflow,
  duplicateWorkflow,
} from "@features/workflow/lib/workflow-storage";
import { getWorkflowRouteRef } from "@features/workflow/lib/workflow-storage-helpers";
import { type WorkflowGalleryTab } from "./types";

interface WorkflowGalleryActionsArgs {
  newFolderName: string;
  setNewFolderName: (value: string) => void;
  newWorkflowName: string;
  setNewWorkflowName: (value: string) => void;
  setSelectedTab: (value: WorkflowGalleryTab) => void;
  setShowNewFolderDialog: (value: boolean) => void;
  setShowNewWorkflowDialog: (value: boolean) => void;
  setShowFilterPopover: (value: boolean) => void;
}

export const useWorkflowGalleryActions = (
  state: WorkflowGalleryActionsArgs,
) => {
  const navigate = useNavigate();

  const handleOpenWorkflow = useCallback(
    (workflowId: string) => {
      navigate(`/workflow-canvas/${workflowId}`);
    },
    [navigate],
  );

  const handleCreateFolder = useCallback(() => {
    toast({
      title: "Folder creation coming soon",
      description: state.newFolderName
        ? `We'll create "${state.newFolderName}" once persistence is wired up.`
        : "Folder creation will be available in a future update.",
    });

    state.setNewFolderName("");
    state.setShowNewFolderDialog(false);
  }, [state]);

  const handleCreateWorkflow = useCallback(async () => {
    const name = state.newWorkflowName.trim() || "Untitled Workflow";

    try {
      const workflow = await createWorkflow({
        name,
        description: "",
        tags: ["draft"],
        nodes: [],
        edges: [],
      });

      state.setNewWorkflowName("");
      state.setShowNewWorkflowDialog(false);
      state.setSelectedTab("all");

      toast({
        title: "Workflow created",
        description: `"${workflow.name}" is ready to edit.`,
      });

      handleOpenWorkflow(getWorkflowRouteRef(workflow));
    } catch (error) {
      toast({
        title: "Failed to create workflow",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  }, [handleOpenWorkflow, state]);

  const handleUseTemplate = useCallback(
    async (templateId: string) => {
      try {
        const workflow = await createWorkflowFromTemplate(templateId);
        if (!workflow) {
          toast({
            title: "Template unavailable",
            description: "We couldn't find that template. Please try another.",
            variant: "destructive",
          });
          return;
        }

        state.setSelectedTab("all");

        toast({
          title: "Template copied",
          description: `"${workflow.name}" has been added to your workspace.`,
        });

        handleOpenWorkflow(getWorkflowRouteRef(workflow));
      } catch (error) {
        toast({
          title: "Failed to create workflow from template",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    },
    [handleOpenWorkflow, state],
  );

  const handleDuplicateWorkflow = useCallback(
    async (workflowId: string) => {
      try {
        const copy = await duplicateWorkflow(workflowId);
        if (!copy) {
          toast({
            title: "Duplicate failed",
            description:
              "We couldn't duplicate this workflow. Please try again.",
            variant: "destructive",
          });
          return;
        }

        state.setSelectedTab("all");

        toast({
          title: "Workflow duplicated",
          description: `"${copy.name}" is ready to edit.`,
        });

        handleOpenWorkflow(getWorkflowRouteRef(copy));
      } catch (error) {
        toast({
          title: "Failed to duplicate workflow",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    },
    [handleOpenWorkflow, state],
  );

  const handleExportWorkflow = useCallback((workflow: Workflow) => {
    try {
      const payload = {
        name: workflow.name,
        description: workflow.description,
        nodes: workflow.nodes,
        edges: workflow.edges,
      };
      const serialized = JSON.stringify(payload, null, 2);
      const blob = new Blob([serialized], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${
        workflow.name.replace(/\s+/g, "-").toLowerCase() || "workflow"
      }.json`;
      anchor.click();
      URL.revokeObjectURL(url);

      toast({
        title: "Workflow exported",
        description: `Downloaded ${workflow.name}.json`,
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description:
          error instanceof Error ? error.message : "Unable to export workflow.",
        variant: "destructive",
      });
    }
  }, []);

  const handleDeleteWorkflow = useCallback(
    async (workflowId: string, workflowName: string) => {
      try {
        await deleteWorkflow(workflowId);
        toast({
          title: "Workflow deleted",
          description: `"${workflowName}" has been removed from your workspace.`,
        });
      } catch (error) {
        toast({
          title: "Failed to delete workflow",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    },
    [],
  );

  const handleApplyFilters = useCallback(() => {
    toast({
      title: "Filters applied",
      description:
        "Filter changes will affect the gallery once data wiring is complete.",
    });
    state.setShowFilterPopover(false);
  }, [state]);

  return {
    handleOpenWorkflow,
    handleCreateFolder,
    handleCreateWorkflow,
    handleUseTemplate,
    handleDuplicateWorkflow,
    handleExportWorkflow,
    handleDeleteWorkflow,
    handleApplyFilters,
  };
};
