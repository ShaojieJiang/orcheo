import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";
import {
  applyCronTriggerConfig,
  applyDelayConfig,
  applyHttpPollingTriggerConfig,
  applyManualTriggerConfig,
  applyMongoConfig,
  applySetVariableConfig,
  applySlackConfig,
  applySwitchConfig,
  applyTelegramConfig,
  applyWebhookTriggerConfig,
  applyWhileConfig,
  createDecisionEdgeNodeConfig,
} from "@features/workflow/lib/graph-config/node-handlers";
import {
  DECISION_NODE_TYPES,
  DEFAULT_NODE_CODE,
} from "@features/workflow/lib/graph-config/constants";
import type {
  CanvasNode,
  NodeProcessingArtifacts,
  NodeProcessingContext,
} from "@features/workflow/lib/graph-config/types";

const getBackendType = (node: CanvasNode): string | undefined => {
  const data = node.data ?? {};
  const raw = data?.backendType;
  if (typeof raw === "string" && raw.trim().length > 0) {
    return raw.trim();
  }
  return undefined;
};

export const processNodes = async (
  nodes: CanvasNode[],
  context: NodeProcessingContext,
): Promise<NodeProcessingArtifacts> => {
  const { canvasToGraph, maybeYield, warnings } = context;

  const graphNodes: Array<Record<string, unknown>> = [
    { name: "START", type: "START" },
  ];
  const graphEdgeNodes: Array<Record<string, unknown>> = [];
  const executableNodes: CanvasNode[] = [];
  const branchPathByCanvasId: Record<string, string> = {};
  const defaultBranchKeyByCanvasId: Record<string, string | undefined> = {};
  const decisionNodeNameByCanvasId: Record<string, string> = {};
  const decisionNodeTypeByCanvasId: Record<string, string> = {};

  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
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
    const nodeName = canvasToGraph[node.id];

    const baseConfig: Record<string, unknown> = {
      name: nodeName,
      type: backendType,
      display_name: node.data?.label ?? node.id ?? `Node ${index + 1}`,
      canvas_id: node.id,
    };

    if (DECISION_NODE_TYPES.has(backendType)) {
      decisionNodeNameByCanvasId[node.id] = nodeName;
      decisionNodeTypeByCanvasId[node.id] = backendType;
      const edgeNodeConfig = createDecisionEdgeNodeConfig({
        node,
        backendType,
        baseConfig,
      });
      graphEdgeNodes.push(edgeNodeConfig);
      await maybeYield();
      continue;
    }

    const nodeConfig: Record<string, unknown> = { ...baseConfig };

    if (backendType === "PythonCode") {
      nodeConfig.code = code;
    }

    if (backendType === "SwitchNode") {
      applySwitchConfig({
        node,
        data,
        nodeConfig,
        canvasToGraph,
        branchPathByCanvasId,
        defaultBranchKeyByCanvasId,
      });
    }

    if (backendType === "WhileNode") {
      applyWhileConfig({
        node,
        data,
        nodeConfig,
        canvasToGraph,
        branchPathByCanvasId,
      });
    }

    if (backendType === "SetVariableNode") {
      await applySetVariableConfig(data, nodeConfig, warnings, maybeYield);
    }

    if (backendType === "DelayNode") {
      applyDelayConfig(data, nodeConfig);
    }

    if (backendType === "MongoDBNode") {
      applyMongoConfig(data, nodeConfig);
    }

    if (backendType === "SlackNode") {
      applySlackConfig(data, nodeConfig);
    }

    if (backendType === "MessageTelegram") {
      applyTelegramConfig(data, nodeConfig);
    }

    if (backendType === "CronTriggerNode") {
      applyCronTriggerConfig(data, nodeConfig);
    }

    if (backendType === "ManualTriggerNode") {
      applyManualTriggerConfig(data, nodeConfig);
    }

    if (backendType === "HttpPollingTriggerNode") {
      applyHttpPollingTriggerConfig(data, nodeConfig);
    }

    if (backendType === "WebhookTriggerNode") {
      applyWebhookTriggerConfig(data, nodeConfig);
    }

    graphNodes.push(nodeConfig);
    executableNodes.push(node);
    await maybeYield();
  }

  return {
    graphNodes,
    graphEdgeNodes,
    executableNodes,
    branchPathByCanvasId,
    defaultBranchKeyByCanvasId,
    decisionNodeNameByCanvasId,
    decisionNodeTypeByCanvasId,
  };
};
