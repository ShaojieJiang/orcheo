import type { Node, Edge } from "@xyflow/react";

/**
 * Find all upstream (previous) nodes that connect to the target node.
 * Returns nodes in topological order (closest dependencies first).
 *
 * @param targetNodeId - The ID of the node to find upstream nodes for
 * @param nodes - All nodes in the workflow
 * @param edges - All edges in the workflow
 * @returns Array of upstream nodes in topological order
 */
export function findUpstreamNodes(
  targetNodeId: string,
  nodes: Node[],
  edges: Edge[],
): Node[] {
  const upstreamIds = new Set<string>();
  const visited = new Set<string>();
  const queue: string[] = [targetNodeId];

  // BFS to find all upstream nodes
  while (queue.length > 0) {
    const currentId = queue.shift()!;
    if (visited.has(currentId)) continue;
    visited.add(currentId);

    // Find all edges that point to this node
    const incomingEdges = edges.filter((edge) => edge.target === currentId);

    for (const edge of incomingEdges) {
      if (edge.source !== targetNodeId) {
        upstreamIds.add(edge.source);
      }
      queue.push(edge.source);
    }
  }

  // Convert IDs to nodes
  const upstreamNodes = nodes.filter((node) => upstreamIds.has(node.id));

  // Sort in topological order (nodes with no incoming edges first)
  return topologicalSort(upstreamNodes, edges);
}

/**
 * Check if a node has any incoming connections.
 *
 * @param nodeId - The ID of the node to check
 * @param edges - All edges in the workflow
 * @returns True if the node has incoming connections
 */
export function hasIncomingConnections(nodeId: string, edges: Edge[]): boolean {
  return edges.some((edge) => edge.target === nodeId);
}

/**
 * Collect outputs from all upstream nodes.
 * Returns a merged object with all outputs keyed by node ID.
 *
 * @param upstreamNodes - Array of upstream nodes
 * @returns Object with outputs keyed by node ID
 */
type RuntimeSummary = {
  outputs?: unknown;
  messages?: unknown;
  raw?: unknown;
};

export function collectUpstreamOutputs(
  upstreamNodes: Node[],
  runtimeCache?: Record<string, RuntimeSummary>,
): Record<string, unknown> {
  const outputs: Record<string, unknown> = {};

  for (const node of upstreamNodes) {
    // Extract runtime outputs from node data
    const runtimeFromNode = node.data?.runtime as RuntimeSummary | undefined;
    const cachedRuntime = runtimeCache?.[node.id];

    const mergedRuntime =
      runtimeFromNode || cachedRuntime
        ? {
            ...(runtimeFromNode ?? {}),
            ...(cachedRuntime ?? {}),
          }
        : undefined;

    if (mergedRuntime) {
      // Prioritize outputs, then messages, then raw
      const nodeOutput =
        mergedRuntime.outputs ?? mergedRuntime.messages ?? mergedRuntime.raw;

      if (nodeOutput !== undefined) {
        outputs[node.id] = nodeOutput;
      }
    }
  }

  return outputs;
}

/**
 * Sort nodes in topological order based on edges.
 * Nodes with no dependencies come first.
 *
 * @param nodes - Nodes to sort
 * @param edges - Edges defining dependencies
 * @returns Sorted array of nodes
 */
function topologicalSort(nodes: Node[], edges: Edge[]): Node[] {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();

  // Initialize
  for (const node of nodes) {
    inDegree.set(node.id, 0);
    adjacency.set(node.id, []);
  }

  // Build adjacency list and in-degree count
  for (const edge of edges) {
    if (nodeMap.has(edge.source) && nodeMap.has(edge.target)) {
      adjacency.get(edge.source)!.push(edge.target);
      inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
    }
  }

  // Kahn's algorithm
  const queue: string[] = [];
  const result: Node[] = [];

  // Start with nodes that have no incoming edges
  for (const [nodeId, degree] of inDegree.entries()) {
    if (degree === 0) {
      queue.push(nodeId);
    }
  }

  while (queue.length > 0) {
    const nodeId = queue.shift()!;
    const node = nodeMap.get(nodeId);
    if (node) {
      result.push(node);
    }

    // Reduce in-degree for neighbors
    for (const neighbor of adjacency.get(nodeId) || []) {
      const newDegree = (inDegree.get(neighbor) || 0) - 1;
      inDegree.set(neighbor, newDegree);
      if (newDegree === 0) {
        queue.push(neighbor);
      }
    }
  }

  return result;
}
