import type { NodeProps } from "@xyflow/react";
import type React from "react";

export type NodeStatus = "idle" | "running" | "success" | "error";

export type NodeHandleConfig = {
  id?: string;
  label?: string;
  position?: "left" | "right" | "top" | "bottom";
};

export type WorkflowNodeData = {
  label: string;
  description?: string;
  icon?: React.ReactNode;
  iconKey?: string;
  status?: NodeStatus;
  type?: string;
  backendType?: string;
  isDisabled?: boolean;
  onLabelChange?: (id: string, newLabel: string) => void;
  onNodeInspect?: (id: string) => void;
  onDelete?: (id: string) => void;
  isSearchMatch?: boolean;
  isSearchActive?: boolean;
  inputs?: NodeHandleConfig[];
  outputs?: NodeHandleConfig[];
  hideInputHandle?: boolean;
  [key: string]: unknown;
};

export type WorkflowNodeProps = NodeProps<WorkflowNodeData>;
