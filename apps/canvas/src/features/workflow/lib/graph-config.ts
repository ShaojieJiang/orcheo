import type { Edge, Node } from "@xyflow/react";
import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";

type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

type CanvasNode = Node<{
  label?: string;
  type?: string;
  status?: NodeStatus;
  [key: string]: unknown;
}>;

type CanvasEdge = Edge<Record<string, unknown>>;

export interface GraphBuildResult {
  config: {
    nodes: Array<Record<string, unknown>>;
    edges: Array<{ source: string; target: string }>;
    conditional_edges?: Array<{
      source: string;
      path: string;
      mapping: Record<string, string>;
      default?: string;
    }>;
  };
  canvasToGraph: Record<string, string>;
  graphToCanvas: Record<string, string>;
}

const DEFAULT_NODE_CODE = "return state";

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null && !Array.isArray(value);
};

const toStringRecord = (value: unknown): Record<string, string> => {
  if (!isRecord(value)) {
    return {};
  }

  return Object.entries(value).reduce<Record<string, string>>(
    (acc, [key, rawValue]) => {
      if (typeof key !== "string") {
        return acc;
      }

      if (typeof rawValue === "string") {
        acc[key] = rawValue;
        return acc;
      }

      if (typeof rawValue === "number" || typeof rawValue === "boolean") {
        acc[key] = String(rawValue);
        return acc;
      }

      return acc;
    },
    {},
  );
};

const slugify = (value: string, fallback: string): string => {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
  return slug || fallback;
};

const ensureUniqueName = (candidate: string, used: Set<string>): string => {
  if (!used.has(candidate)) {
    used.add(candidate);
    return candidate;
  }
  let counter = 2;
  while (used.has(`${candidate}-${counter}`)) {
    counter += 1;
  }
  const unique = `${candidate}-${counter}`;
  used.add(unique);
  return unique;
};

const shouldSerializeNode = (node: CanvasNode): boolean => {
  const semanticTypeRaw =
    typeof node.data?.type === "string"
      ? node.data.type.toLowerCase()
      : undefined;
  const canvasType = typeof node.type === "string" ? node.type : undefined;

  if (semanticTypeRaw === "annotation" || canvasType === "stickyNote") {
    return false;
  }

  return true;
};

export const buildGraphConfigFromCanvas = (
  nodes: CanvasNode[],
  edges: CanvasEdge[],
): GraphBuildResult => {
  const canvasToGraph: Record<string, string> = {};
  const graphToCanvas: Record<string, string> = {};
  const usedNames = new Set<string>();
  const branchPathByCanvasId: Record<string, string> = {};
  const defaultBranchKeyByCanvasId: Record<string, string | undefined> = {};

  const serializableNodes = nodes.filter(shouldSerializeNode);

  const getBackendType = (node: CanvasNode): string | undefined => {
    const data = node.data ?? {};
    const raw = data?.backendType;
    if (typeof raw === "string" && raw.trim().length > 0) {
      return raw.trim();
    }
    return undefined;
  };

  serializableNodes.forEach((node, index) => {
    const label = String(node.data?.label ?? node.id ?? `node-${index + 1}`);
    const base = slugify(label, `node-${index + 1}`);
    const unique = ensureUniqueName(base, usedNames);
    canvasToGraph[node.id] = unique;
    graphToCanvas[unique] = node.id;
  });

  const graphNodes: Array<Record<string, unknown>> = [
    { name: "START", type: "START" },
    ...serializableNodes.map((node, index) => {
      const data = node.data ?? {};
      const semanticTypeRaw =
        typeof data?.type === "string" ? data.type.toLowerCase() : undefined;
      const defaultCode =
        semanticTypeRaw === "python" ? DEFAULT_PYTHON_CODE : DEFAULT_NODE_CODE;
      const code =
        typeof data?.code === "string" && data.code.length > 0
          ? data.code
          : defaultCode;

      const backendType = getBackendType(node) ?? "PythonCode";

      const nodeConfig: Record<string, unknown> = {
        name: canvasToGraph[node.id],
        type: backendType,
        display_name: node.data?.label ?? node.id ?? `Node ${index + 1}`,
        canvas_id: node.id,
      };

      if (backendType === "PythonCode") {
        nodeConfig.code = code;
      }

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

        nodeConfig.conditions = normalisedConditions.map(
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
        nodeConfig.condition_logic =
          typeof data?.conditionLogic === "string"
            ? data.conditionLogic
            : "and";
        branchPathByCanvasId[node.id] =
          `results.${canvasToGraph[node.id]}.branch`;
      }

      if (backendType === "SwitchNode") {
        nodeConfig.value = data?.value ?? null;
        nodeConfig.case_sensitive = data?.caseSensitive ?? true;
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
        branchPathByCanvasId[node.id] =
          `results.${canvasToGraph[node.id]}.branch`;
      }

      if (backendType === "WhileNode") {
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
          typeof data?.conditionLogic === "string"
            ? data.conditionLogic
            : "and";
        if (
          typeof data?.maxIterations === "number" &&
          Number.isFinite(data.maxIterations)
        ) {
          nodeConfig.max_iterations = data.maxIterations;
        }
        branchPathByCanvasId[node.id] =
          `results.${canvasToGraph[node.id]}.branch`;
      }

      if (backendType === "SetVariableNode") {
        nodeConfig.target_path = data?.targetPath ?? "context.value";
        nodeConfig.value = data?.value ?? null;
      }

      if (backendType === "DelayNode") {
        const delayValue = data?.durationSeconds;
        const parsed =
          typeof delayValue === "number" ? delayValue : Number(delayValue ?? 0);
        nodeConfig.duration_seconds = Number.isFinite(parsed) ? parsed : 0;
      }

      if (backendType === "MongoDBNode") {
        if (typeof data?.database === "string" && data.database.length > 0) {
          nodeConfig.database = data.database;
        }
        if (
          typeof data?.collection === "string" &&
          data.collection.length > 0
        ) {
          nodeConfig.collection = data.collection;
        }
        nodeConfig.operation =
          typeof data?.operation === "string" && data.operation.length > 0
            ? data.operation
            : "find";
        nodeConfig.query = isRecord(data?.query) ? data.query : {};
      }

      if (backendType === "SlackNode") {
        if (typeof data?.tool_name === "string" && data.tool_name.length > 0) {
          nodeConfig.tool_name = data.tool_name;
        }
        nodeConfig.kwargs = isRecord(data?.kwargs) ? data.kwargs : {};
      }

      if (backendType === "MessageTelegram") {
        if (typeof data?.token === "string" && data.token.length > 0) {
          nodeConfig.token = data.token;
        }
        if (typeof data?.chat_id === "string" && data.chat_id.length > 0) {
          nodeConfig.chat_id = data.chat_id;
        }
        if (typeof data?.message === "string" && data.message.length > 0) {
          nodeConfig.message = data.message;
        }
        if (
          typeof data?.parse_mode === "string" &&
          data.parse_mode.length > 0
        ) {
          nodeConfig.parse_mode = data.parse_mode;
        }
      }

      if (backendType === "CronTriggerNode") {
        nodeConfig.expression =
          typeof data?.expression === "string" && data.expression.length > 0
            ? data.expression
            : "0 * * * *";
        nodeConfig.timezone =
          typeof data?.timezone === "string" && data.timezone.length > 0
            ? data.timezone
            : "UTC";
        nodeConfig.allow_overlapping = Boolean(data?.allow_overlapping);
        if (typeof data?.start_at === "string" && data.start_at.length > 0) {
          nodeConfig.start_at = data.start_at;
        }
        if (typeof data?.end_at === "string" && data.end_at.length > 0) {
          nodeConfig.end_at = data.end_at;
        }
      }

      if (backendType === "ManualTriggerNode") {
        nodeConfig.label =
          typeof data?.label === "string" && data.label.length > 0
            ? data.label
            : "manual";
        nodeConfig.allowed_actors = Array.isArray(data?.allowed_actors)
          ? (data.allowed_actors as string[])
          : [];
        nodeConfig.require_comment = Boolean(data?.require_comment);
        nodeConfig.default_payload = isRecord(data?.default_payload)
          ? data.default_payload
          : {};
        const cooldownValue = data?.cooldown_seconds;
        const parsedCooldown =
          typeof cooldownValue === "number"
            ? cooldownValue
            : Number(cooldownValue ?? 0);
        nodeConfig.cooldown_seconds = Number.isFinite(parsedCooldown)
          ? parsedCooldown
          : 0;
      }

      if (backendType === "HttpPollingTriggerNode") {
        nodeConfig.url =
          typeof data?.url === "string" && data.url.length > 0 ? data.url : "";
        nodeConfig.method =
          typeof data?.method === "string" && data.method.length > 0
            ? data.method
            : "GET";
        nodeConfig.headers = isRecord(data?.headers) ? data.headers : {};
        nodeConfig.query_params = isRecord(data?.query_params)
          ? data.query_params
          : {};
        if (isRecord(data?.body)) {
          nodeConfig.body = data.body;
        }
        const intervalValue = data?.interval_seconds;
        const parsedInterval =
          typeof intervalValue === "number"
            ? intervalValue
            : Number(intervalValue ?? 0);
        nodeConfig.interval_seconds = Number.isFinite(parsedInterval)
          ? parsedInterval
          : 300;
        const timeoutValue = data?.timeout_seconds;
        const parsedTimeout =
          typeof timeoutValue === "number"
            ? timeoutValue
            : Number(timeoutValue ?? 0);
        nodeConfig.timeout_seconds = Number.isFinite(parsedTimeout)
          ? parsedTimeout
          : 30;
        nodeConfig.verify_tls = data?.verify_tls !== false;
        nodeConfig.follow_redirects = Boolean(data?.follow_redirects);
        if (
          typeof data?.deduplicate_on === "string" &&
          data.deduplicate_on.length > 0
        ) {
          nodeConfig.deduplicate_on = data.deduplicate_on;
        }
      }

      if (backendType === "WebhookTriggerNode") {
        const allowedMethodsRaw = Array.isArray(data?.allowed_methods)
          ? (data.allowed_methods as unknown[])
          : [];
        const allowedMethods = allowedMethodsRaw
          .filter(
            (method): method is string =>
              typeof method === "string" && method.trim().length > 0,
          )
          .map((method) => method.trim().toUpperCase());

        nodeConfig.allowed_methods =
          allowedMethods.length > 0 ? allowedMethods : ["POST"];
        nodeConfig.required_headers = toStringRecord(data?.required_headers);
        nodeConfig.required_query_params = toStringRecord(
          data?.required_query_params,
        );

        if (
          typeof data?.shared_secret_header === "string" &&
          data.shared_secret_header.length > 0
        ) {
          nodeConfig.shared_secret_header = data.shared_secret_header;
        }

        if (
          typeof data?.shared_secret === "string" &&
          data.shared_secret.length > 0
        ) {
          nodeConfig.shared_secret = data.shared_secret;
        }

        const rateLimitRaw = data?.rate_limit;
        if (isRecord(rateLimitRaw)) {
          const limitValue = rateLimitRaw.limit;
          const intervalValue = rateLimitRaw.interval_seconds;
          const parsedLimit =
            typeof limitValue === "number"
              ? limitValue
              : Number(limitValue ?? NaN);
          const parsedInterval =
            typeof intervalValue === "number"
              ? intervalValue
              : Number(intervalValue ?? NaN);

          if (Number.isFinite(parsedLimit) && Number.isFinite(parsedInterval)) {
            nodeConfig.rate_limit = {
              limit: Math.max(1, Math.trunc(parsedLimit)),
              interval_seconds: Math.max(1, Math.trunc(parsedInterval)),
            };
          }
        }
      }

      return nodeConfig;
    }),
    { name: "END", type: "END" },
  ];

  const graphEdges: Array<{ source: string; target: string }> = [];
  const conditionalEdgesMap: Record<
    string,
    { path: string; mapping: Record<string, string>; defaultTarget?: string }
  > = {};

  edges.forEach((edge) => {
    const source = canvasToGraph[edge.source];
    const target = canvasToGraph[edge.target];
    if (!source || !target) {
      return;
    }

    const branchPath = branchPathByCanvasId[edge.source];
    const defaultBranchKey = defaultBranchKeyByCanvasId[edge.source];
    const rawHandle =
      typeof edge.sourceHandle === "string" && edge.sourceHandle.length > 0
        ? edge.sourceHandle.trim()
        : undefined;

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
      return;
    }

    graphEdges.push({ source, target });
  });

  const conditionalEdges = Object.entries(conditionalEdgesMap)
    .map(([source, entry]) => {
      if (Object.keys(entry.mapping).length === 0 && !entry.defaultTarget) {
        return null;
      }
      const payload: {
        source: string;
        path: string;
        mapping: Record<string, string>;
        default?: string;
      } = {
        source,
        path: entry.path,
        mapping: entry.mapping,
      };
      if (entry.defaultTarget) {
        payload.default = entry.defaultTarget;
      }
      return payload;
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);

  if (serializableNodes.length === 0) {
    graphEdges.push({ source: "START", target: "END" });
  } else {
    const incoming = new Set(graphEdges.map((edge) => edge.target));
    const outgoing = new Set(graphEdges.map((edge) => edge.source));

    conditionalEdges.forEach((entry) => {
      Object.values(entry.mapping).forEach((target) => incoming.add(target));
      if (entry.default) {
        incoming.add(entry.default);
      }
      outgoing.add(entry.source);
    });

    serializableNodes.forEach((node) => {
      const graphName = canvasToGraph[node.id];
      if (!incoming.has(graphName)) {
        graphEdges.push({ source: "START", target: graphName });
      }
      if (!outgoing.has(graphName)) {
        graphEdges.push({ source: graphName, target: "END" });
      }
    });
  }

  const config: GraphBuildResult["config"] = {
    nodes: graphNodes,
    edges: graphEdges,
  };

  if (conditionalEdges.length > 0) {
    config.conditional_edges = conditionalEdges;
  }

  return {
    config,
    canvasToGraph,
    graphToCanvas,
  };
};
