import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { executeNode } from "@/lib/api";
import type { NodeInspectorProps, NodeRuntimeCacheEntry } from "./types";
import { isRecord } from "./utils";

interface UseNodeTesterParams {
  node?: NodeInspectorProps["node"];
  backendType: string | null;
  draftData: Record<string, unknown>;
  liveInputs: unknown;
  upstreamOutputs: Record<string, unknown>;
  useLiveData: boolean;
  onCacheRuntime?: (nodeId: string, runtime: NodeRuntimeCacheEntry) => void;
}

interface UseNodeTesterReturn {
  isTestingNode: boolean;
  testResult: unknown;
  testError: string | null;
  handleTestNode: () => Promise<void>;
}

const buildNodeConfig = (
  node: NonNullable<NodeInspectorProps["node"]>,
  draftData: Record<string, unknown>,
  backendType: string,
): Record<string, unknown> => {
  const nodeConfig: Record<string, unknown> = {
    name: node.id,
    ...draftData,
  };

  delete nodeConfig.runtime;
  delete nodeConfig.label;
  delete nodeConfig.description;
  delete nodeConfig.iconKey;
  delete nodeConfig.backendType;
  delete nodeConfig.type;

  nodeConfig.type = backendType;

  if (
    backendType === "SetVariableNode" &&
    Array.isArray(nodeConfig.variables)
  ) {
    const variablesArray = nodeConfig.variables as Array<
      Record<string, unknown>
    >;
    const variablesDict: Record<string, unknown> = {};

    for (const variable of variablesArray) {
      if (!variable?.name) continue;

      const variableName = String(variable.name);
      const valueType =
        typeof variable.valueType === "string" ? variable.valueType : "string";
      let typedValue = variable.value ?? null;

      if (typedValue !== null && typedValue !== undefined) {
        switch (valueType) {
          case "number":
            typedValue = Number(typedValue);
            break;
          case "boolean":
            typedValue =
              typedValue === true || typedValue === "true" || typedValue === 1;
            break;
          case "object":
            if (typeof typedValue === "string") {
              try {
                typedValue = JSON.parse(typedValue);
              } catch {
                console.warn(
                  `Failed to parse object value for ${variableName}, using empty object`,
                );
                typedValue = {};
              }
            }
            break;
          default:
            typedValue = String(typedValue);
        }
      }

      variablesDict[variableName] = typedValue;
    }

    nodeConfig.variables = variablesDict;
  }

  return nodeConfig;
};

export function useNodeTester({
  node,
  backendType,
  draftData,
  liveInputs,
  upstreamOutputs,
  useLiveData,
  onCacheRuntime,
}: UseNodeTesterParams): UseNodeTesterReturn {
  const [isTestingNode, setIsTestingNode] = useState(false);
  const [testResult, setTestResult] = useState<unknown>(null);
  const [testError, setTestError] = useState<string | null>(null);

  useEffect(() => {
    setTestResult(null);
    setTestError(null);
  }, [node?.id]);

  const handleTestNode = useCallback(async () => {
    if (!node) {
      toast.error("Cannot test node: node not found");
      return;
    }

    const resolvedBackendType =
      typeof draftData?.backendType === "string"
        ? (draftData.backendType as string)
        : backendType;

    if (!resolvedBackendType) {
      toast.error(
        "Cannot test node: missing backend type information. This node may not support testing yet.",
      );
      return;
    }

    setIsTestingNode(true);
    setTestError(null);
    setTestResult(null);

    try {
      const nodeConfig = buildNodeConfig(node, draftData, resolvedBackendType);

      let inputs: Record<string, unknown> = {};

      if (useLiveData && isRecord(liveInputs)) {
        inputs = { ...liveInputs };
      } else if (Object.keys(upstreamOutputs).length > 0) {
        inputs = { ...upstreamOutputs };
      }

      const response = await executeNode({
        node_config: nodeConfig,
        inputs,
      });

      if (response.status === "success") {
        setTestResult(response.result);
        const timestamp = new Date().toISOString();
        const cachedInputs = { ...inputs };
        const runtimeUpdate: NodeRuntimeCacheEntry = {
          ...(Object.keys(cachedInputs).length > 0
            ? { inputs: cachedInputs }
            : {}),
          raw: response.result,
          updatedAt: timestamp,
        };

        if (response.result !== undefined) {
          if (isRecord(response.result)) {
            const resultRecord = response.result as Record<string, unknown>;
            if (resultRecord.outputs !== undefined) {
              runtimeUpdate.outputs = resultRecord.outputs;
            } else if (runtimeUpdate.outputs === undefined) {
              runtimeUpdate.outputs = response.result;
            }
            if (resultRecord.messages !== undefined) {
              runtimeUpdate.messages = resultRecord.messages;
            }
          } else {
            runtimeUpdate.outputs = response.result;
          }
        }

        onCacheRuntime?.(node.id, runtimeUpdate);
        toast.success("Node executed successfully");
      } else {
        setTestError(response.error || "Unknown error");
        toast.error("Node execution failed");
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to execute node";
      setTestError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsTestingNode(false);
    }
  }, [
    backendType,
    draftData,
    liveInputs,
    node,
    onCacheRuntime,
    upstreamOutputs,
    useLiveData,
  ]);

  return {
    isTestingNode,
    testResult,
    testError,
    handleTestNode,
  };
}
