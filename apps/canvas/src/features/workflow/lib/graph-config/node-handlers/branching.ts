import type { CanvasNode } from "@features/workflow/lib/graph-config/types";

interface BranchingContext {
  node: CanvasNode;
  data: Record<string, unknown>;
  nodeConfig: Record<string, unknown>;
  canvasToGraph: Record<string, string>;
  branchPathByCanvasId: Record<string, string>;
  defaultBranchKeyByCanvasId: Record<string, string | undefined>;
}

interface DecisionNodeParams {
  node: CanvasNode;
  backendType: string;
  baseConfig: Record<string, unknown>;
}

export const createDecisionEdgeNodeConfig = ({
  node,
  backendType,
  baseConfig,
}: DecisionNodeParams): Record<string, unknown> => {
  const data = node.data ?? {};
  const edgeNodeConfig: Record<string, unknown> = { ...baseConfig };

  if (backendType === "IfElseNode") {
    const conditionsRaw = Array.isArray(data?.conditions)
      ? (data.conditions as Array<Record<string, unknown>>)
      : [];
    const normalisedConditions =
      conditionsRaw.length > 0
        ? conditionsRaw
        : [
            {
              left: null,
              operator: "equals",
              right: null,
              caseSensitive: true,
            },
          ];

    edgeNodeConfig.conditions = normalisedConditions.map(
      (condition, conditionIndex) => ({
        left: condition?.left ?? null,
        operator:
          typeof condition?.operator === "string"
            ? (condition.operator as string)
            : "equals",
        right: condition?.right ?? null,
        case_sensitive:
          typeof condition?.caseSensitive === "boolean"
            ? (condition.caseSensitive as boolean)
            : true,
        id:
          typeof condition?.id === "string"
            ? condition.id
            : `condition-${conditionIndex + 1}`,
      }),
    );
    edgeNodeConfig.condition_logic =
      typeof data?.conditionLogic === "string" ? data.conditionLogic : "and";
  }

  return edgeNodeConfig;
};

export const applySwitchConfig = ({
  node,
  data,
  nodeConfig,
  canvasToGraph,
  branchPathByCanvasId,
  defaultBranchKeyByCanvasId,
}: BranchingContext): void => {
  const casesRaw = Array.isArray(data?.cases)
    ? (data.cases as Array<Record<string, unknown>>)
    : [];
  const normalisedCases =
    casesRaw.length > 0
      ? casesRaw
      : [
          {
            label: "Case 1",
            match: null,
            branchKey: "case_1",
          },
        ];

  nodeConfig.value = data?.value ?? null;
  nodeConfig.case_sensitive = data?.caseSensitive ?? true;
  nodeConfig.cases = normalisedCases.map((caseEntry, caseIndex) => {
    const rawBranchKey =
      typeof caseEntry?.branchKey === "string" &&
      caseEntry.branchKey.trim().length > 0
        ? (caseEntry.branchKey as string).trim()
        : `case_${caseIndex + 1}`;
    return {
      label:
        typeof caseEntry?.label === "string"
          ? (caseEntry.label as string)
          : undefined,
      match: caseEntry?.match ?? null,
      branch_key: rawBranchKey,
      case_sensitive:
        typeof caseEntry?.caseSensitive === "boolean"
          ? (caseEntry.caseSensitive as boolean)
          : undefined,
    };
  });

  const defaultBranchKey =
    typeof data?.defaultBranchKey === "string" &&
    data.defaultBranchKey.trim().length > 0
      ? (data.defaultBranchKey as string).trim()
      : "default";
  nodeConfig.default_branch_key = defaultBranchKey;
  defaultBranchKeyByCanvasId[node.id] = defaultBranchKey;
  branchPathByCanvasId[node.id] = `results.${canvasToGraph[node.id]}.branch`;
};

export const applyWhileConfig = ({
  node,
  data,
  nodeConfig,
  canvasToGraph,
  branchPathByCanvasId,
}: Omit<BranchingContext, "defaultBranchKeyByCanvasId">): void => {
  const conditionsRaw = Array.isArray(data?.conditions)
    ? (data.conditions as Array<Record<string, unknown>>)
    : [];
  const normalisedConditions =
    conditionsRaw.length > 0
      ? conditionsRaw
      : [
          {
            left: null,
            operator: "less_than",
            right: null,
            caseSensitive: true,
          },
        ];

  nodeConfig.conditions = normalisedConditions.map(
    (condition, conditionIndex) => ({
      left: condition?.left ?? null,
      operator:
        typeof condition?.operator === "string"
          ? (condition.operator as string)
          : "less_than",
      right: condition?.right ?? null,
      case_sensitive:
        typeof condition?.caseSensitive === "boolean"
          ? (condition.caseSensitive as boolean)
          : true,
      id:
        typeof condition?.id === "string"
          ? condition.id
          : `condition-${conditionIndex + 1}`,
    }),
  );
  nodeConfig.condition_logic =
    typeof data?.conditionLogic === "string" ? data.conditionLogic : "and";
  if (
    typeof data?.maxIterations === "number" &&
    Number.isFinite(data.maxIterations)
  ) {
    nodeConfig.max_iterations = data.maxIterations;
  }

  branchPathByCanvasId[node.id] = `results.${canvasToGraph[node.id]}.branch`;
};
