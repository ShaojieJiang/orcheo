import { Edge, MarkerType, Node } from "@xyflow/react";
import {
  getNodeIcon,
  inferNodeIconKey,
} from "@features/workflow/lib/node-icons";
import type {
  WorkflowExecution,
  WorkflowNode,
} from "./workflow-execution-history.types";

export const defaultNodeStyle = {
  background: "none",
  border: "none",
  padding: 0,
  borderRadius: 0,
  width: "auto",
  boxShadow: "none",
};

export const determineReactFlowNodeType = (
  type: string | undefined,
): "default" | "chatTrigger" | "startEnd" => {
  if (type === "chatTrigger") {
    return "chatTrigger";
  }
  if (type === "start" || type === "end") {
    return "startEnd";
  }
  return "default";
};

export const normaliseNodeStatus = (
  status: WorkflowNode["status"],
): "idle" | "running" | "success" | "error" => {
  switch (status) {
    case "running":
      return "running";
    case "success":
      return "success";
    case "error":
      return "error";
    case "warning":
      return "running";
    default:
      return "idle";
  }
};

export const parseChatTriggerDescription = (
  details: WorkflowNode["details"],
): string | undefined => {
  if (!details) {
    return undefined;
  }
  if (typeof details.message === "string" && details.message.trim()) {
    return details.message;
  }
  if (typeof details.description === "string" && details.description.trim()) {
    return details.description;
  }
  return undefined;
};

export const formatExecutionDate = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();

  if (date.toDateString() === now.toDateString()) {
    return `Today, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }

  const yesterday = new Date();
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `Yesterday, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }

  return (
    date.toLocaleDateString([], {
      month: "short",
      day: "numeric",
      year: "numeric",
    }) +
    `, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
  );
};

export const formatDuration = (ms: number) => {
  if (ms < 1000) return `${ms}ms`;
  const seconds = ms / 1000;
  return `${seconds.toFixed(1)}s`;
};

export const getStatusBadgeClass = (status: string) => {
  switch (status.toLowerCase()) {
    case "success":
      return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    case "failed":
      return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
    case "partial":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400";
    case "running":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400";
  }
};

export const getReactFlowNodes = (
  execution: WorkflowExecution | null,
): Node[] => {
  if (!execution) return [];

  return execution.nodes.map((node) => {
    const semanticType = typeof node.type === "string" ? node.type : "default";
    const reactFlowType = determineReactFlowNodeType(semanticType);
    const status = normaliseNodeStatus(node.status);

    if (reactFlowType === "startEnd") {
      return {
        id: node.id,
        type: reactFlowType,
        position: node.position,
        style: defaultNodeStyle,
        width: 64,
        height: 64,
        data: {
          label: node.name,
          type: semanticType === "end" ? "end" : "start",
        },
      } as Node;
    }

    if (reactFlowType === "chatTrigger") {
      return {
        id: node.id,
        type: reactFlowType,
        position: node.position,
        style: defaultNodeStyle,
        width: 180,
        height: 120,
        data: {
          label: node.name,
          type: "chatTrigger",
          description: parseChatTriggerDescription(node.details),
          status,
        },
      } as Node;
    }

    const iconKey =
      node.iconKey ??
      inferNodeIconKey({
        iconKey: node.iconKey,
        label: node.name,
        type: semanticType,
      });

    return {
      id: node.id,
      type: reactFlowType,
      position: node.position,
      style: defaultNodeStyle,
      width: 64,
      height: 64,
      data: {
        label: node.name,
        status,
        type: semanticType,
        iconKey,
        icon: iconKey ? getNodeIcon(iconKey) : undefined,
      },
    } as Node;
  });
};

export const getReactFlowEdges = (
  execution: WorkflowExecution | null,
): Edge[] => {
  if (!execution) return [];

  return execution.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "default",
    animated: execution.status === "running",
    style: { stroke: "#99a1b3", strokeWidth: 2 },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 12,
      height: 12,
    },
  }));
};
