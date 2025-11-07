import type { TerminalConnectionParams } from "@features/workflow/lib/graph-config/types";

export const ensureTerminalConnections = async ({
  executableNodes,
  canvasToGraph,
  graphEdges,
  conditionalEdges,
  maybeYield,
}: TerminalConnectionParams): Promise<void> => {
  if (executableNodes.length === 0) {
    graphEdges.push({ source: "START", target: "END" });
    return;
  }

  const incoming = new Set(graphEdges.map((edge) => edge.target));
  const outgoing = new Set(graphEdges.map((edge) => edge.source));

  for (const entry of conditionalEdges) {
    Object.values(entry.mapping).forEach((target) => incoming.add(target));
    if (entry.default) {
      incoming.add(entry.default);
    }
    outgoing.add(entry.source);
    await maybeYield();
  }

  for (const node of executableNodes) {
    const graphName = canvasToGraph[node.id];
    if (!incoming.has(graphName)) {
      graphEdges.push({ source: "START", target: graphName });
    }
    if (!outgoing.has(graphName)) {
      graphEdges.push({ source: graphName, target: "END" });
    }
    await maybeYield();
  }
};
