import { generateRandomId } from "@features/workflow/pages/workflow-canvas/helpers/id";

import type {
  CanvasEdge,
  CanvasNode,
  NodeStatus,
  WorkflowExecution,
  WorkflowExecutionNode,
} from "@features/workflow/pages/workflow-canvas/helpers/types";

export function createExecutionRecord(
  executionId: string,
  nodes: CanvasNode[],
  edges: CanvasEdge[],
  graphToCanvas: Record<string, string>,
): WorkflowExecution {
  const startTime = new Date();
  const executionNodes: WorkflowExecutionNode[] = nodes.map((node) => ({
    id: node.id,
    type:
      typeof node.data?.type === "string"
        ? node.data.type
        : (node.type ?? "custom"),
    name:
      typeof node.data?.label === "string" && node.data.label.trim()
        ? node.data.label
        : node.id,
    position: node.position,
    status: "running",
    iconKey:
      typeof node.data?.iconKey === "string" ? node.data.iconKey : undefined,
  }));

  const executionEdges: CanvasEdge[] = edges.map((edge) => ({
    id: edge.id ?? generateRandomId("edge"),
    source: edge.source,
    target: edge.target,
  }));

  return {
    id: executionId,
    runId: executionId,
    status: "running",
    startTime: startTime.toISOString(),
    duration: 0,
    issues: 0,
    nodes: executionNodes,
    edges: executionEdges,
    logs: [
      {
        timestamp: startTime.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        level: "INFO" as const,
        message: "Workflow execution started",
      },
    ],
    metadata: { graphToCanvas },
  };
}

export function markNodesAsRunning(nodes: CanvasNode[]): CanvasNode[] {
  return nodes.map((node) => ({
    ...node,
    data: { ...node.data, status: "running" as NodeStatus },
  }));
}
