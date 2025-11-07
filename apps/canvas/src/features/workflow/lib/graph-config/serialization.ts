import type { CanvasNode } from "@features/workflow/lib/graph-config/types";

const shouldSerializeNode = (node: CanvasNode): boolean => {
  const semanticTypeRaw =
    typeof node.data?.type === "string"
      ? node.data.type.toLowerCase()
      : undefined;
  const canvasType = typeof node.type === "string" ? node.type : undefined;

  if (
    semanticTypeRaw === "annotation" ||
    semanticTypeRaw === "start" ||
    semanticTypeRaw === "end" ||
    canvasType === "stickyNote"
  ) {
    return false;
  }

  return true;
};

export const filterSerializableNodes = (nodes: CanvasNode[]): CanvasNode[] => {
  return nodes.filter(shouldSerializeNode);
};

export const countSerializableVariables = (nodes: CanvasNode[]): number => {
  return nodes.reduce((count, node) => {
    const variables = node.data?.variables;
    return Array.isArray(variables) ? count + variables.length : count;
  }, 0);
};
