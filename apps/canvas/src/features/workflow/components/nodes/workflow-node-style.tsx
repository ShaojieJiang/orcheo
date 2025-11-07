import React from "react";
import { AlertCircle, CheckCircle, Clock } from "lucide-react";

import type { NodeStatus } from "./workflow-node.types";

type StatusIconMap = Record<NodeStatus, React.ReactNode>;

const statusIconMap: StatusIconMap = {
  idle: <Clock className="h-4 w-4 text-muted-foreground" />,
  running: <Clock className="h-4 w-4 text-blue-500 animate-pulse" />,
  success: <CheckCircle className="h-4 w-4 text-green-500" />,
  error: <AlertCircle className="h-4 w-4 text-red-500" />,
};

type NodeColorKey =
  | "default"
  | "api"
  | "function"
  | "trigger"
  | "data"
  | "ai"
  | "python";

const nodeColorPalette: Record<NodeColorKey, string> = {
  default: "bg-card border-border",
  api: "bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-800/50",
  function:
    "bg-purple-50 border-purple-200 dark:bg-purple-950/30 dark:border-purple-800/50",
  trigger:
    "bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-800/50",
  data: "bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800/50",
  ai: "bg-indigo-50 border-indigo-200 dark:bg-indigo-950/30 dark:border-indigo-800/50",
  python:
    "bg-orange-50 border-orange-200 dark:bg-orange-950/30 dark:border-orange-800/50",
};

export const getStatusIcon = (status: NodeStatus): React.ReactNode =>
  statusIconMap[status];

export const getNodeColor = (type?: string): string => {
  if (!type) {
    return nodeColorPalette.default;
  }
  if (
    Object.prototype.hasOwnProperty.call(nodeColorPalette, type as NodeColorKey)
  ) {
    return nodeColorPalette[type as NodeColorKey];
  }
  return nodeColorPalette.default;
};
