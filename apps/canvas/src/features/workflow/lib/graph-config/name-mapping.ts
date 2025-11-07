import {
  ensureUniqueName,
  slugify,
} from "@features/workflow/lib/graph-config/utils";
import type {
  CanvasNode,
  GraphNameMaps,
  MaybeYieldFn,
} from "@features/workflow/lib/graph-config/types";

export const buildGraphNameMaps = async (
  nodes: CanvasNode[],
  maybeYield: MaybeYieldFn,
): Promise<GraphNameMaps> => {
  const canvasToGraph: Record<string, string> = {};
  const graphToCanvas: Record<string, string> = {};
  const usedNames = new Set<string>();

  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    const label = String(node.data?.label ?? node.id ?? `node-${index + 1}`);
    const base = slugify(label, `node-${index + 1}`);
    const unique = ensureUniqueName(base, usedNames);
    canvasToGraph[node.id] = unique;
    graphToCanvas[unique] = node.id;
    await maybeYield();
  }

  return { canvasToGraph, graphToCanvas };
};
