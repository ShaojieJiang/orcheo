import type {
  CanvasEdge,
  CanvasNode,
  GraphBuildResult,
} from "@features/workflow/lib/graph-config/types";
import { buildGraphNameMaps } from "@features/workflow/lib/graph-config/name-mapping";
import { createYieldController } from "@features/workflow/lib/graph-config/workload";
import {
  countSerializableVariables,
  filterSerializableNodes,
} from "@features/workflow/lib/graph-config/serialization";
import { processNodes } from "@features/workflow/lib/graph-config/node-processing";
import { processEdges } from "@features/workflow/lib/graph-config/edge-processing";
import { ensureTerminalConnections } from "@features/workflow/lib/graph-config/terminal-connections";

export type { GraphBuildResult } from "@features/workflow/lib/graph-config/types";

export const buildGraphConfigFromCanvas = async (
  nodes: CanvasNode[],
  edges: CanvasEdge[],
): Promise<GraphBuildResult> => {
  const serializableNodes = filterSerializableNodes(nodes);
  const totalVariableCount = countSerializableVariables(serializableNodes);
  const totalWorkItems =
    serializableNodes.length * 3 + edges.length + totalVariableCount;

  const { maybeYield } = createYieldController(totalWorkItems);
  const warnings: string[] = [];

  const { canvasToGraph, graphToCanvas } = await buildGraphNameMaps(
    serializableNodes,
    maybeYield,
  );

  const nodeArtifacts = await processNodes(serializableNodes, {
    canvasToGraph,
    maybeYield,
    warnings,
  });

  nodeArtifacts.graphNodes.push({ name: "END", type: "END" });

  const { graphEdges, conditionalEdges } = await processEdges({
    edges,
    canvasToGraph,
    branchPathByCanvasId: nodeArtifacts.branchPathByCanvasId,
    defaultBranchKeyByCanvasId: nodeArtifacts.defaultBranchKeyByCanvasId,
    decisionNodeNameByCanvasId: nodeArtifacts.decisionNodeNameByCanvasId,
    decisionNodeTypeByCanvasId: nodeArtifacts.decisionNodeTypeByCanvasId,
    maybeYield,
  });

  await ensureTerminalConnections({
    executableNodes: nodeArtifacts.executableNodes,
    canvasToGraph,
    graphEdges,
    conditionalEdges,
    maybeYield,
  });

  const config: GraphBuildResult["config"] = {
    nodes: nodeArtifacts.graphNodes,
    edges: graphEdges,
  };

  if (nodeArtifacts.graphEdgeNodes.length > 0) {
    config.edge_nodes = nodeArtifacts.graphEdgeNodes;
  }

  if (conditionalEdges.length > 0) {
    config.conditional_edges = conditionalEdges;
  }

  return {
    config,
    canvasToGraph,
    graphToCanvas,
    warnings,
  };
};
