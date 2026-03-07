import { toStoredWorkflow } from "./workflow-storage-helpers";
import {
  API_BASE,
  fetchWorkflow,
  fetchWorkflowVersions,
  request,
} from "./workflow-storage-api";
import type {
  ApiWorkflowVersion,
  StoredWorkflow,
  WorkflowRunnableConfig,
} from "./workflow-storage.types";

export const ensureWorkflow = async (
  workflowId: string,
): Promise<StoredWorkflow | undefined> => {
  const [workflow, versions] = await Promise.all([
    fetchWorkflow(workflowId),
    fetchWorkflowVersions(workflowId),
  ]);
  if (!workflow) {
    return undefined;
  }
  return toStoredWorkflow(workflow, versions);
};

const resolveTargetVersion = (
  versions: ApiWorkflowVersion[],
  versionNumber?: number,
): number => {
  if (versions.length === 0) {
    throw new Error(
      "Canvas can only save config for workflows with an existing Python version. Ingest a Python script first.",
    );
  }
  if (versionNumber !== undefined) {
    const matched = versions.find((entry) => entry.version === versionNumber);
    if (!matched) {
      throw new Error(`Workflow version ${versionNumber} not found.`);
    }
    return versionNumber;
  }
  return Math.max(...versions.map((entry) => entry.version));
};

export const persistRunnableConfig = async (
  workflowId: string,
  actor: string,
  runnableConfig: WorkflowRunnableConfig | null,
  versionNumber?: number,
) => {
  const versions = await fetchWorkflowVersions(workflowId);
  const targetVersion = resolveTargetVersion(versions, versionNumber);
  await request(
    `${API_BASE}/${workflowId}/versions/${targetVersion}/runnable-config`,
    {
      method: "PUT",
      body: JSON.stringify({
        runnable_config: runnableConfig,
        actor,
      }),
    },
  );
};
