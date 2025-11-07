import type {
  ConditionalEdge,
  EdgeProcessingParams,
  EdgeProcessingResult,
  GraphEdge,
} from "@features/workflow/lib/graph-config/types";

export const processEdges = async ({
  edges,
  canvasToGraph,
  branchPathByCanvasId,
  defaultBranchKeyByCanvasId,
  decisionNodeNameByCanvasId,
  decisionNodeTypeByCanvasId,
  maybeYield,
}: EdgeProcessingParams): Promise<EdgeProcessingResult> => {
  const graphEdges: GraphEdge[] = [];
  const conditionalEdges: ConditionalEdge[] = [];
  const conditionalEdgesMap: Record<
    string,
    { path: string; mapping: Record<string, string>; defaultTarget?: string }
  > = {};
  const decisionSourcesByCanvasId: Record<string, Set<string>> = {};
  const decisionOutgoingByCanvasId: Record<
    string,
    { mapping: Record<string, string>; defaultTarget?: string }
  > = {};

  for (const edge of edges) {
    const sourceId = edge.source;
    const targetId = edge.target;
    const source = canvasToGraph[sourceId];
    const target = canvasToGraph[targetId];
    if (!source || !target) {
      await maybeYield();
      continue;
    }

    if (decisionNodeNameByCanvasId[targetId]) {
      const sources = decisionSourcesByCanvasId[targetId] ?? new Set<string>();
      sources.add(source);
      decisionSourcesByCanvasId[targetId] = sources;
      await maybeYield();
      continue;
    }

    const rawHandle =
      typeof edge.sourceHandle === "string" && edge.sourceHandle.length > 0
        ? edge.sourceHandle.trim()
        : undefined;

    if (decisionNodeNameByCanvasId[sourceId]) {
      const entry = decisionOutgoingByCanvasId[sourceId] ?? {
        mapping: {},
        defaultTarget: undefined,
      };
      const decisionType = decisionNodeTypeByCanvasId[sourceId];
      const normalisedHandle =
        rawHandle && decisionType === "IfElseNode"
          ? rawHandle.toLowerCase()
          : rawHandle;

      if (normalisedHandle) {
        entry.mapping[normalisedHandle] = target;
      } else if (!entry.defaultTarget) {
        entry.defaultTarget = target;
      }

      decisionOutgoingByCanvasId[sourceId] = entry;
      await maybeYield();
      continue;
    }

    const branchPath = branchPathByCanvasId[sourceId];
    const defaultBranchKey = defaultBranchKeyByCanvasId[sourceId];

    if (branchPath) {
      const entry = conditionalEdgesMap[source] ?? {
        path: branchPath,
        mapping: {},
        defaultTarget: undefined,
      };

      if (rawHandle && defaultBranchKey && rawHandle === defaultBranchKey) {
        entry.defaultTarget = target;
      } else if (rawHandle) {
        entry.mapping[rawHandle] = target;
      } else if (!rawHandle && defaultBranchKey) {
        entry.defaultTarget = target;
      }

      conditionalEdgesMap[source] = entry;
      await maybeYield();
      continue;
    }

    graphEdges.push({ source, target });
    await maybeYield();
  }

  for (const [source, entry] of Object.entries(conditionalEdgesMap)) {
    if (Object.keys(entry.mapping).length === 0 && !entry.defaultTarget) {
      await maybeYield();
      continue;
    }
    const payload: ConditionalEdge = {
      source,
      path: entry.path,
      mapping: entry.mapping,
    };
    if (entry.defaultTarget) {
      payload.default = entry.defaultTarget;
    }
    conditionalEdges.push(payload);
    await maybeYield();
  }

  for (const [decisionId, sources] of Object.entries(
    decisionSourcesByCanvasId,
  )) {
    const decisionName = decisionNodeNameByCanvasId[decisionId];
    const outgoing = decisionOutgoingByCanvasId[decisionId];
    if (!decisionName || !outgoing) {
      await maybeYield();
      continue;
    }
    if (Object.keys(outgoing.mapping).length === 0 && !outgoing.defaultTarget) {
      await maybeYield();
      continue;
    }
    const sourceList = sources.size > 0 ? Array.from(sources) : [decisionName];
    for (const source of sourceList) {
      const payload: ConditionalEdge = {
        source,
        path: decisionName,
        mapping: { ...outgoing.mapping },
      };
      if (outgoing.defaultTarget) {
        payload.default = outgoing.defaultTarget;
      }
      conditionalEdges.push(payload);
      await maybeYield();
    }
  }

  return { graphEdges, conditionalEdges };
};
