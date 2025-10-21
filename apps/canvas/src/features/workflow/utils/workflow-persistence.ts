/**
 * Utilities for persisting workflow canvas state and computing diffs.
 */

export type NodeStatus = "idle" | "running" | "success" | "error" | "warning";

export interface PersistedNodeData {
  type?: string;
  label?: string;
  description?: string;
  status?: NodeStatus;
  isDisabled?: boolean;
  [key: string]: unknown;
}

export interface PersistedNode {
  id: string;
  type?: string;
  position: { x: number; y: number };
  data: PersistedNodeData;
}

export interface PersistedEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  label?: string;
  type?: string;
  animated?: boolean;
  data?: Record<string, unknown>;
}

export interface PersistedSnapshot {
  nodes: PersistedNode[];
  edges: PersistedEdge[];
}

export interface WorkflowDiffFieldChange {
  before?: unknown;
  after?: unknown;
}

export interface WorkflowDiffEntry {
  type: "node" | "edge";
  change: "added" | "removed" | "modified";
  id: string;
  label?: string;
  details?: Record<string, WorkflowDiffFieldChange>;
}

export interface WorkflowDiff {
  entries: WorkflowDiffEntry[];
  added: number;
  removed: number;
  modified: number;
}

export interface WorkflowVersionRecord {
  id: string;
  version: string;
  timestamp: string;
  author: {
    name: string;
    avatar: string;
  };
  message: string;
  snapshot: PersistedSnapshot;
  changes: {
    added: number;
    removed: number;
    modified: number;
  };
}

export interface PersistedWorkflow {
  id: string;
  name: string;
  versions: WorkflowVersionRecord[];
  currentVersion?: string;
}

interface StorageAdapter {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const STORAGE_KEY = "orcheo.workflow.persistence";
const DEFAULT_AUTHOR = {
  name: "Avery Chen",
  avatar: "https://avatar.vercel.sh/avery",
};
const memoryStore = new Map<string, string>();
let storageAdapter: StorageAdapter | null = null;

const getStorage = (): StorageAdapter => {
  if (storageAdapter) {
    return storageAdapter;
  }

  try {
    if (typeof window !== "undefined" && window.localStorage) {
      const testKey = "__orcheo_persistence_test__";
      window.localStorage.setItem(testKey, "ok");
      window.localStorage.removeItem(testKey);
      storageAdapter = window.localStorage;
      return storageAdapter;
    }
  } catch {
    // ignore access errors (private mode, SSR, etc.)
  }

  try {
    const globalStorage = (globalThis as { localStorage?: StorageAdapter })
      .localStorage;
    if (globalStorage) {
      storageAdapter = globalStorage;
      return storageAdapter;
    }
  } catch {
    // ignore
  }

  storageAdapter = {
    getItem: (key: string) => memoryStore.get(key) ?? null,
    setItem: (key: string, value: string) => {
      memoryStore.set(key, value);
    },
    removeItem: (key: string) => {
      memoryStore.delete(key);
    },
  } satisfies StorageAdapter;

  return storageAdapter;
};

const isSerializable = (value: unknown, seen = new Set<unknown>()): boolean => {
  if (value === null) {
    return true;
  }

  const valueType = typeof value;
  if (
    valueType === "string" ||
    valueType === "number" ||
    valueType === "boolean"
  ) {
    return true;
  }

  if (
    valueType === "function" ||
    valueType === "symbol" ||
    valueType === "bigint"
  ) {
    return false;
  }

  if (Array.isArray(value)) {
    if (seen.has(value)) {
      return false;
    }
    seen.add(value);
    return value.every((item) => isSerializable(item, seen));
  }

  if (valueType === "object") {
    if (seen.has(value)) {
      return false;
    }
    seen.add(value);
    return Object.values(value as Record<string, unknown>).every((item) =>
      isSerializable(item, seen),
    );
  }

  return false;
};

const sanitiseNodeData = (
  data: Record<string, unknown> | undefined,
): PersistedNodeData => {
  if (!data) {
    return {};
  }

  const sanitized: PersistedNodeData = {};

  if (typeof data.label === "string") {
    sanitized.label = data.label;
  }
  if (typeof data.description === "string") {
    sanitized.description = data.description;
  }
  if (typeof data.status === "string") {
    sanitized.status = data.status as NodeStatus;
  }
  if (typeof data.type === "string") {
    sanitized.type = data.type;
  }
  if (typeof data.isDisabled === "boolean") {
    sanitized.isDisabled = data.isDisabled;
  }

  for (const [key, value] of Object.entries(data)) {
    if (
      key === "label" ||
      key === "description" ||
      key === "status" ||
      key === "type" ||
      key === "isDisabled" ||
      key === "icon" ||
      key === "onOpenChat"
    ) {
      continue;
    }
    if (isSerializable(value)) {
      sanitized[key] = value;
    }
  }

  return sanitized;
};

const sanitiseEdgeData = (data: Record<string, unknown> | undefined) => {
  if (!data) {
    return undefined;
  }

  const sanitized: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (isSerializable(value)) {
      sanitized[key] = value;
    }
  }

  return Object.keys(sanitized).length > 0 ? sanitized : undefined;
};

const readStore = (): Record<string, PersistedWorkflow> => {
  const storage = getStorage();
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw) as Record<string, PersistedWorkflow>;
    if (parsed && typeof parsed === "object") {
      return parsed;
    }
  } catch {
    // ignore invalid JSON and fall through
  }

  return {};
};

const writeStore = (store: Record<string, PersistedWorkflow>) => {
  const storage = getStorage();
  storage.setItem(STORAGE_KEY, JSON.stringify(store));
};

const cloneWorkflow = (workflow: PersistedWorkflow): PersistedWorkflow => {
  return JSON.parse(JSON.stringify(workflow)) as PersistedWorkflow;
};

const areValuesEqual = (left: unknown, right: unknown): boolean => {
  return JSON.stringify(left) === JSON.stringify(right);
};

const diffNode = (
  current: PersistedNode,
  previous: PersistedNode,
): Record<string, WorkflowDiffFieldChange> | null => {
  const changes: Record<string, WorkflowDiffFieldChange> = {};

  if (
    current.position.x !== previous.position.x ||
    current.position.y !== previous.position.y
  ) {
    changes.position = {
      before: previous.position,
      after: current.position,
    };
  }

  const trackedFields: (keyof PersistedNodeData)[] = [
    "label",
    "description",
    "status",
    "type",
    "isDisabled",
  ];

  for (const field of trackedFields) {
    if (!areValuesEqual(current.data[field], previous.data[field])) {
      changes[field] = {
        before: previous.data[field],
        after: current.data[field],
      };
    }
  }

  const currentExtras = { ...current.data };
  const previousExtras = { ...previous.data };
  for (const field of trackedFields) {
    delete currentExtras[field];
    delete previousExtras[field];
  }

  const extraKeys = new Set([
    ...Object.keys(currentExtras),
    ...Object.keys(previousExtras),
  ]);
  for (const key of extraKeys) {
    if (!areValuesEqual(currentExtras[key], previousExtras[key])) {
      changes[`data.${key}`] = {
        before: previousExtras[key],
        after: currentExtras[key],
      };
    }
  }

  return Object.keys(changes).length > 0 ? changes : null;
};

const diffEdge = (
  current: PersistedEdge,
  previous: PersistedEdge,
): Record<string, WorkflowDiffFieldChange> | null => {
  const changes: Record<string, WorkflowDiffFieldChange> = {};

  if (
    current.source !== previous.source ||
    current.target !== previous.target
  ) {
    changes.connection = {
      before: { source: previous.source, target: previous.target },
      after: { source: current.source, target: current.target },
    };
  }

  const trackedFields: (keyof PersistedEdge)[] = ["label", "type", "animated"];

  for (const field of trackedFields) {
    if (!areValuesEqual(current[field], previous[field])) {
      changes[field] = {
        before: previous[field],
        after: current[field],
      };
    }
  }

  const currentData = current.data ?? {};
  const previousData = previous.data ?? {};
  const dataKeys = new Set([
    ...Object.keys(currentData),
    ...Object.keys(previousData),
  ]);
  for (const key of dataKeys) {
    if (!areValuesEqual(currentData[key], previousData[key])) {
      changes[`data.${key}`] = {
        before: previousData[key],
        after: currentData[key],
      };
    }
  }

  return Object.keys(changes).length > 0 ? changes : null;
};

export function createPersistedSnapshot(
  nodes: Array<{
    id: string;
    type?: string;
    position?: { x?: number; y?: number };
    data?: Record<string, unknown>;
  }>,
  edges: Array<{
    id: string;
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
    label?: string;
    type?: string;
    animated?: boolean;
    data?: Record<string, unknown>;
  }>,
): PersistedSnapshot {
  const persistedNodes: PersistedNode[] = nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: {
      x: typeof node.position?.x === "number" ? node.position.x : 0,
      y: typeof node.position?.y === "number" ? node.position.y : 0,
    },
    data: sanitiseNodeData(node.data),
  }));

  const persistedEdges: PersistedEdge[] = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle ?? null,
    targetHandle: edge.targetHandle ?? null,
    label: edge.label,
    type: edge.type,
    animated: edge.animated ?? false,
    data: sanitiseEdgeData(edge.data),
  }));

  return {
    nodes: persistedNodes,
    edges: persistedEdges,
  };
}

export function computeWorkflowDiff(
  current: PersistedSnapshot,
  previous?: PersistedSnapshot,
): WorkflowDiff {
  const previousNodes = new Map(
    (previous?.nodes ?? []).map((node) => [node.id, node] as const),
  );
  const previousEdges = new Map(
    (previous?.edges ?? []).map((edge) => [edge.id, edge] as const),
  );

  const entries: WorkflowDiffEntry[] = [];

  for (const node of current.nodes) {
    const prior = previousNodes.get(node.id);
    if (!prior) {
      entries.push({
        type: "node",
        change: "added",
        id: node.id,
        label: node.data.label,
      });
      continue;
    }

    const changes = diffNode(node, prior);
    if (changes) {
      entries.push({
        type: "node",
        change: "modified",
        id: node.id,
        label: node.data.label ?? prior.data.label,
        details: changes,
      });
    }
  }

  for (const node of previousNodes.values()) {
    if (!current.nodes.some((candidate) => candidate.id === node.id)) {
      entries.push({
        type: "node",
        change: "removed",
        id: node.id,
        label: node.data.label,
      });
    }
  }

  for (const edge of current.edges) {
    const prior = previousEdges.get(edge.id);
    if (!prior) {
      entries.push({
        type: "edge",
        change: "added",
        id: edge.id,
        label: edge.label ?? `${edge.source} → ${edge.target}`,
      });
      continue;
    }

    const changes = diffEdge(edge, prior);
    if (changes) {
      entries.push({
        type: "edge",
        change: "modified",
        id: edge.id,
        label: edge.label ?? prior.label ?? `${edge.source} → ${edge.target}`,
        details: changes,
      });
    }
  }

  for (const edge of previousEdges.values()) {
    if (!current.edges.some((candidate) => candidate.id === edge.id)) {
      entries.push({
        type: "edge",
        change: "removed",
        id: edge.id,
        label: edge.label ?? `${edge.source} → ${edge.target}`,
      });
    }
  }

  const added = entries.filter((entry) => entry.change === "added").length;
  const removed = entries.filter((entry) => entry.change === "removed").length;
  const modified = entries.filter(
    (entry) => entry.change === "modified",
  ).length;

  return {
    entries,
    added,
    removed,
    modified,
  };
}

export function loadWorkflow(workflowId: string): PersistedWorkflow | null {
  const store = readStore();
  const workflow = store[workflowId];
  if (!workflow) {
    return null;
  }
  return cloneWorkflow(workflow);
}

interface SaveOptions {
  name: string;
  snapshot: PersistedSnapshot;
  message?: string;
  author?: {
    name: string;
    avatar: string;
  };
}

export function saveWorkflowVersion(
  workflowId: string,
  { name, snapshot, message, author }: SaveOptions,
): PersistedWorkflow {
  const store = readStore();
  const existing = store[workflowId];
  const versions = existing?.versions ?? [];
  const previousSnapshot = versions.at(-1)?.snapshot;
  const diff = computeWorkflowDiff(snapshot, previousSnapshot);

  const versionIndex = versions.length + 1;
  const versionLabel = `v${versionIndex}`;

  const newVersion: WorkflowVersionRecord = {
    id: `${workflowId}-${versionIndex}`,
    version: versionLabel,
    timestamp: new Date().toISOString(),
    author: author ?? DEFAULT_AUTHOR,
    message: message ?? "Manual save",
    snapshot,
    changes: {
      added: diff.added,
      removed: diff.removed,
      modified: diff.modified,
    },
  };

  const updatedWorkflow: PersistedWorkflow = {
    id: workflowId,
    name,
    versions: [...versions, newVersion],
    currentVersion: versionLabel,
  };

  store[workflowId] = updatedWorkflow;
  writeStore(store);

  return cloneWorkflow(updatedWorkflow);
}

export function deleteWorkflow(workflowId: string): void {
  const store = readStore();
  if (store[workflowId]) {
    delete store[workflowId];
    writeStore(store);
  }
}

export function clearAllWorkflows(): void {
  const storage = getStorage();
  storage.removeItem(STORAGE_KEY);
  memoryStore.clear();
  storageAdapter = null;
}
