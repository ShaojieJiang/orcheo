import type { ReactNode } from "react";

import {
  getNodeIcon,
  type NodeIconKey,
} from "@features/workflow/lib/node-icons";

export interface NodeCategory {
  id: string;
  name: string;
  icon: ReactNode;
  nodes: SidebarNode[];
}

export interface SidebarNodeData {
  label: string;
  type: string;
  description: string;
  iconKey: NodeIconKey;
  backendType?: string;
  [key: string]: unknown;
}

export interface SidebarNode {
  id: string;
  name: string;
  description: string;
  iconKey: NodeIconKey;
  icon?: ReactNode;
  type: string;
  backendType?: string;
  data: SidebarNodeData;
}

export interface BuildSidebarNodeParams {
  id: string;
  name: string;
  description: string;
  iconKey: NodeIconKey;
  type: string;
  backendType?: string;
  data?: Record<string, unknown>;
}

export const buildSidebarNode = ({
  id,
  name,
  description,
  iconKey,
  type,
  backendType,
  data,
}: BuildSidebarNodeParams): SidebarNode => {
  const mergedData: SidebarNodeData = {
    label: name,
    type,
    description,
    ...(data ?? {}),
    iconKey,
    ...(backendType ? { backendType } : {}),
  };

  return {
    id,
    name,
    description,
    iconKey,
    icon: getNodeIcon(iconKey),
    type,
    backendType,
    data: mergedData,
  };
};
