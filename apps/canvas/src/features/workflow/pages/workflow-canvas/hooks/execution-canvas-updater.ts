import type {
  CanvasNode,
  NodeData,
  NodeRuntimeData,
  NodeStatus,
  WorkflowExecutionStatus,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

interface CanvasNodeUpdateParams {
  nodes: CanvasNode[];
  nodeUpdates: Record<string, NodeStatus>;
  runtimeUpdates: Record<string, NodeRuntimeData>;
  executionStatus: WorkflowExecutionStatus | null;
}

export function updateCanvasNodes({
  nodes,
  nodeUpdates,
  runtimeUpdates,
  executionStatus,
}: CanvasNodeUpdateParams): CanvasNode[] {
  const shouldUpdate =
    Object.keys(nodeUpdates).length > 0 ||
    Object.keys(runtimeUpdates).length > 0 ||
    (executionStatus && executionStatus !== "running");

  if (!shouldUpdate) {
    return nodes;
  }

  return nodes.map((node) => {
    const nextStatus = nodeUpdates[node.id];
    const runtime = runtimeUpdates[node.id];
    let nextData = node.data as NodeData;
    let changed = false;

    if (nextStatus) {
      nextData = { ...nextData, status: nextStatus };
      changed = true;
    } else if (
      executionStatus &&
      executionStatus !== "running" &&
      (node.data?.status === "running" || node.data?.status === undefined)
    ) {
      const fallback: NodeStatus =
        executionStatus === "failed"
          ? "error"
          : executionStatus === "partial"
            ? "warning"
            : "success";
      nextData = { ...nextData, status: fallback };
      changed = true;
    }

    if (runtime) {
      const nextRuntime: NodeRuntimeData = {
        ...((nextData.runtime ?? {}) as NodeRuntimeData),
        ...(runtime.inputs !== undefined ? { inputs: runtime.inputs } : {}),
        ...(runtime.outputs !== undefined ? { outputs: runtime.outputs } : {}),
        ...(runtime.messages !== undefined
          ? { messages: runtime.messages }
          : {}),
        raw: runtime.raw,
        updatedAt: runtime.updatedAt,
      };
      nextData = { ...nextData, runtime: nextRuntime };
      changed = true;
    }

    if (changed) {
      return {
        ...node,
        data: nextData,
      };
    }

    return node;
  });
}
