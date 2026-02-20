import { useState } from "react";

import type { StoredWorkflow } from "@features/workflow/lib/workflow-storage";

export function useWorkflowMetadataState() {
  const [workflowName, setWorkflowName] = useState("New Workflow");
  const [workflowDescription, setWorkflowDescription] = useState("");
  const [currentWorkflowId, setCurrentWorkflowId] = useState<string | null>(
    null,
  );
  const [workflowVersions, setWorkflowVersions] = useState<
    StoredWorkflow["versions"]
  >([]);
  const [workflowTags, setWorkflowTags] = useState<string[]>(["draft"]);
  const [isWorkflowLoading, setIsWorkflowLoading] = useState(false);
  const [workflowLoadError, setWorkflowLoadError] = useState<string | null>(
    null,
  );

  return {
    workflowName,
    setWorkflowName,
    workflowDescription,
    setWorkflowDescription,
    currentWorkflowId,
    setCurrentWorkflowId,
    workflowVersions,
    setWorkflowVersions,
    workflowTags,
    setWorkflowTags,
    isWorkflowLoading,
    setIsWorkflowLoading,
    workflowLoadError,
    setWorkflowLoadError,
  };
}
