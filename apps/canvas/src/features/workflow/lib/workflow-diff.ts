import type {
  WorkflowEdge,
  WorkflowNode,
} from "@features/workflow/data/workflow-data";

export interface NodeDiff {
  id: string;
  label: string;
  before?: WorkflowNode;
  after?: WorkflowNode;
}

export interface EdgeDiff {
  id: string;
  before?: WorkflowEdge;
  after?: WorkflowEdge;
}

export interface WorkflowDiffSection<TDiff> {
  added: TDiff[];
  removed: TDiff[];
  modified: TDiff[];
}

export interface WorkflowDiffResult {
  nodes: WorkflowDiffSection<NodeDiff>;
  edges: WorkflowDiffSection<EdgeDiff>;
}

const serializeNode = (node: WorkflowNode) => ({
  id: node.id,
  type: node.type,
  position: node.position,
  data: node.data,
});

const serializeEdge = (edge: WorkflowEdge) => ({
  id: edge.id,
  source: edge.source,
  target: edge.target,
  sourceHandle: edge.sourceHandle,
  targetHandle: edge.targetHandle,
  label: edge.label,
  type: edge.type,
  animated: edge.animated,
  style: edge.style,
});

const nodesEqual = (a: WorkflowNode, b: WorkflowNode) => {
  return JSON.stringify(serializeNode(a)) === JSON.stringify(serializeNode(b));
};

const edgesEqual = (a: WorkflowEdge, b: WorkflowEdge) => {
  return JSON.stringify(serializeEdge(a)) === JSON.stringify(serializeEdge(b));
};

export const diffWorkflowSnapshots = (
  previousNodes: WorkflowNode[],
  previousEdges: WorkflowEdge[],
  nextNodes: WorkflowNode[],
  nextEdges: WorkflowEdge[],
): WorkflowDiffResult => {
  const previousNodeMap = new Map(previousNodes.map((node) => [node.id, node]));
  const nextNodeMap = new Map(nextNodes.map((node) => [node.id, node]));

  const previousEdgeMap = new Map(previousEdges.map((edge) => [edge.id, edge]));
  const nextEdgeMap = new Map(nextEdges.map((edge) => [edge.id, edge]));

  const nodeDiff: WorkflowDiffSection<NodeDiff> = {
    added: [],
    removed: [],
    modified: [],
  };

  const edgeDiff: WorkflowDiffSection<EdgeDiff> = {
    added: [],
    removed: [],
    modified: [],
  };

  nextNodes.forEach((node) => {
    const previous = previousNodeMap.get(node.id);
    if (!previous) {
      nodeDiff.added.push({
        id: node.id,
        label: node.data.label ?? node.id,
        after: node,
      });
      return;
    }

    if (!nodesEqual(previous, node)) {
      nodeDiff.modified.push({
        id: node.id,
        label: node.data.label ?? node.id,
        before: previous,
        after: node,
      });
    }
  });

  previousNodes.forEach((node) => {
    if (!nextNodeMap.has(node.id)) {
      nodeDiff.removed.push({
        id: node.id,
        label: node.data.label ?? node.id,
        before: node,
      });
    }
  });

  nextEdges.forEach((edge) => {
    const previous = previousEdgeMap.get(edge.id);
    if (!previous) {
      edgeDiff.added.push({ id: edge.id, after: edge });
      return;
    }

    if (!edgesEqual(previous, edge)) {
      edgeDiff.modified.push({ id: edge.id, before: previous, after: edge });
    }
  });

  previousEdges.forEach((edge) => {
    if (!nextEdgeMap.has(edge.id)) {
      edgeDiff.removed.push({ id: edge.id, before: edge });
    }
  });

  return {
    nodes: nodeDiff,
    edges: edgeDiff,
  };
};

export const summarizeDiff = (diff: WorkflowDiffResult) => ({
  added: diff.nodes.added.length + diff.edges.added.length,
  removed: diff.nodes.removed.length + diff.edges.removed.length,
  modified: diff.nodes.modified.length + diff.edges.modified.length,
});
