import { buildGraphConfigFromCanvas } from "./graph-config";
import type { WorkflowDiffResult, WorkflowSnapshot } from "./workflow-diff";
import {
  toCanvasEdges,
  toCanvasNodes,
  toStoredWorkflow,
} from "./workflow-storage-helpers";
import {
  API_BASE,
  fetchWorkflow,
  fetchWorkflowVersions,
  request,
} from "./workflow-storage-api";
import type {
  SaveWorkflowInput,
  StoredWorkflow,
  WorkflowRunnableConfig,
} from "./workflow-storage.types";

export const defaultVersionMessage = () =>
  `Updated from canvas on ${new Date().toLocaleString()}`;

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

export const persistVersion = async (
  workflowId: string,
  input: SaveWorkflowInput,
  snapshot: WorkflowSnapshot,
  diff: WorkflowDiffResult,
  actor: string,
  message: string,
  runnableConfig?: WorkflowRunnableConfig | null,
) => {
  const canvasNodes = toCanvasNodes(snapshot.nodes);
  const canvasEdges = toCanvasEdges(snapshot.edges);
  const { config, canvasToGraph, graphToCanvas, warnings } =
    await buildGraphConfigFromCanvas(canvasNodes, canvasEdges);

  if (warnings.length > 0) {
    warnings.forEach((warning) => console.warn(warning));
  }

  await request(`${API_BASE}/${workflowId}/versions`, {
    method: "POST",
    body: JSON.stringify({
      graph: config,
      metadata: {
        canvas: {
          snapshot,
          summary: diff.summary,
          entries: diff.entries,
          message,
          canvasToGraph,
          graphToCanvas,
          tags: input.tags ?? [],
        },
      },
      notes: message,
      created_by: actor,
      runnable_config: runnableConfig,
    }),
  });
};
