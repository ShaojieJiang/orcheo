export const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

export const determineNodeType = (nodeId?: string) => {
  if (nodeId?.includes("chat-trigger")) {
    return "chatTrigger" as const;
  }
  if (nodeId === "sticky-note") {
    return "stickyNote" as const;
  }
  if (nodeId === "start-node" || nodeId === "end-node") {
    return "startEnd" as const;
  }
  return "default" as const;
};

export const validateWorkflowData = (data: unknown) => {
  if (!isRecord(data)) {
    throw new Error("Invalid workflow file structure.");
  }

  const { nodes, edges } = data as {
    nodes: unknown;
    edges: unknown;
  };

  if (!Array.isArray(nodes)) {
    throw new Error("Invalid nodes array in workflow file.");
  }

  nodes.forEach((node, index) => {
    if (!isRecord(node)) {
      throw new Error(`Invalid node at index ${index}.`);
    }
    if (!isRecord(node.position)) {
      throw new Error(`Node ${node.id ?? index} is missing position data.`);
    }
    const { x, y } = node.position as Record<string, unknown>;
    if (typeof x !== "number" || typeof y !== "number") {
      throw new Error(`Node ${node.id ?? index} has invalid coordinates.`);
    }
  });

  if (!Array.isArray(edges)) {
    throw new Error("Invalid edges array in workflow file.");
  }

  edges.forEach((edge, index) => {
    if (!isRecord(edge)) {
      throw new Error(`Invalid edge at index ${index}.`);
    }
    if (typeof edge.source !== "string" || typeof edge.target !== "string") {
      throw new Error(`Edge ${edge.id ?? index} has invalid connections.`);
    }
  });
};
