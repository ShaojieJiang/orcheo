import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";
import type { NodeInspectorProps, NodeRuntimeCacheEntry } from "./types";

export const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

export const extractPythonCode = (
  node?: NodeInspectorProps["node"],
): string => {
  if (!node) {
    return DEFAULT_PYTHON_CODE;
  }
  const candidate = node.data?.code;
  return typeof candidate === "string" && candidate.length > 0
    ? candidate
    : DEFAULT_PYTHON_CODE;
};

export const getSemanticType = (
  node?: NodeInspectorProps["node"],
): string | null => {
  if (!node) {
    return null;
  }
  const dataType = node.data?.type;
  if (typeof dataType === "string" && dataType.length > 0) {
    return dataType.toLowerCase();
  }
  return typeof node.type === "string" && node.type.length > 0
    ? node.type.toLowerCase()
    : null;
};

export const formatUpdatedAt = (timestamp?: string): string | null => {
  if (!timestamp) {
    return null;
  }
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return timestamp;
  }
  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

export const getOutputDisplay = (
  runtime: NodeRuntimeCacheEntry | null,
): {
  outputDisplay: unknown;
  hasLiveOutputs: boolean;
} => {
  if (!runtime) {
    return { outputDisplay: undefined, hasLiveOutputs: false };
  }

  const { outputs, messages, raw } = runtime;
  let display: unknown = raw;

  if (outputs !== undefined || messages !== undefined) {
    const merged: Record<string, unknown> = {};
    if (outputs !== undefined) {
      merged.outputs = outputs as unknown;
    }
    if (messages !== undefined) {
      merged.messages = messages as unknown;
    }
    display =
      outputs !== undefined && messages === undefined ? outputs : merged;
  }

  const hasOutputs =
    outputs !== undefined || messages !== undefined || display !== undefined;

  return {
    outputDisplay: display,
    hasLiveOutputs: hasOutputs,
  };
};
