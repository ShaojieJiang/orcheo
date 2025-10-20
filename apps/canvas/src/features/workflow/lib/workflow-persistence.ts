import type {
  Workflow,
  WorkflowEdge,
  WorkflowNode,
} from "@features/workflow/data/workflow-data";
import {
  diffWorkflowSnapshots,
  summarizeDiff,
} from "@features/workflow/lib/workflow-diff";

export interface WorkflowVersionRecord {
  id: string;
  version: string;
  timestamp: string;
  message: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  author: Workflow["owner"];
  changes: {
    added: number;
    removed: number;
    modified: number;
  };
}

interface WorkflowRecord {
  workflow: Workflow;
  history: WorkflowVersionRecord[];
  versionCounter: number;
}

interface WorkflowStore {
  [workflowId: string]: WorkflowRecord;
}

export interface SaveWorkflowInput {
  id?: string;
  name: string;
  description?: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  tags?: string[];
  owner?: Workflow["owner"];
  lastRun?: Workflow["lastRun"];
  message?: string;
}

export interface SaveWorkflowResult {
  id: string;
  record: WorkflowRecord;
}

const STORAGE_KEY = "orcheo.canvas.workflows.v1";

const DEFAULT_OWNER: Workflow["owner"] = {
  id: "user-1",
  name: "Avery Chen",
  avatar: "https://avatar.vercel.sh/avery",
};

const memoryStorage = new Map<string, string>();

const storage: Storage = (() => {
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage;
  }

  // Fallback storage for non-browser environments (tests, SSR)
  return {
    get length() {
      return memoryStorage.size;
    },
    clear: () => memoryStorage.clear(),
    getItem: (key: string) => memoryStorage.get(key) ?? null,
    key: (index: number) => Array.from(memoryStorage.keys())[index] ?? null,
    removeItem: (key: string) => {
      memoryStorage.delete(key);
    },
    setItem: (key: string, value: string) => {
      memoryStorage.set(key, value);
    },
  } as Storage;
})();

const readStore = (): WorkflowStore => {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw) as WorkflowStore;
    return parsed ?? {};
  } catch (error) {
    console.error("Failed to read workflow store", error);
    return {};
  }
};

const writeStore = (store: WorkflowStore) => {
  storage.setItem(STORAGE_KEY, JSON.stringify(store));
};

const generateWorkflowId = () => {
  if (
    typeof crypto !== "undefined" &&
    "randomUUID" in crypto &&
    typeof crypto.randomUUID === "function"
  ) {
    return `workflow-${crypto.randomUUID()}`;
  }

  const timestamp = Date.now().toString(36);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `workflow-${timestamp}-${randomSuffix}`;
};

const nextVersionLabel = (counter: number) => `1.0.${counter}`;

export const listWorkflows = (): Workflow[] => {
  const store = readStore();
  return Object.values(store)
    .map((entry) => entry.workflow)
    .sort(
      (a, b) =>
        new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    );
};

export const getWorkflowRecord = (workflowId: string) => {
  const store = readStore();
  return store[workflowId] ?? null;
};

export const deleteWorkflow = (workflowId: string) => {
  const store = readStore();
  if (workflowId in store) {
    delete store[workflowId];
    writeStore(store);
  }
};

export const saveWorkflow = (input: SaveWorkflowInput): SaveWorkflowResult => {
  const store = readStore();
  const now = new Date().toISOString();

  const existingRecord = input.id ? store[input.id] : undefined;
  const workflowId = input.id ?? generateWorkflowId();
  const createdAt = existingRecord?.workflow.createdAt ?? now;

  const owner = input.owner ?? existingRecord?.workflow.owner ?? DEFAULT_OWNER;
  const tags = input.tags ?? existingRecord?.workflow.tags ?? ["draft"];

  const workflow: Workflow = {
    id: workflowId,
    name: input.name,
    description:
      input.description ?? existingRecord?.workflow.description ?? "",
    createdAt,
    updatedAt: now,
    owner,
    tags,
    lastRun: input.lastRun ?? existingRecord?.workflow.lastRun,
    nodes: input.nodes,
    edges: input.edges,
  };

  const previousVersion = existingRecord?.history.at(-1) ?? null;
  const diff = diffWorkflowSnapshots(
    previousVersion?.nodes ?? [],
    previousVersion?.edges ?? [],
    input.nodes,
    input.edges,
  );

  const versionAuthor = existingRecord?.workflow.owner ?? owner;
  const versionLabel = nextVersionLabel(existingRecord?.versionCounter ?? 0);

  const historyEntry: WorkflowVersionRecord = {
    id: `version-${workflowId}-${versionLabel}`,
    version: versionLabel,
    timestamp: now,
    message:
      input.message ??
      (existingRecord ? "Updated workflow" : "Initial version"),
    nodes: input.nodes,
    edges: input.edges,
    author: versionAuthor,
    changes: summarizeDiff(diff),
  };

  const history = existingRecord
    ? [...existingRecord.history, historyEntry]
    : [historyEntry];

  const record: WorkflowRecord = {
    workflow,
    history,
    versionCounter: (existingRecord?.versionCounter ?? 0) + 1,
  };

  store[workflowId] = record;
  writeStore(store);

  return { id: workflowId, record };
};

export type { WorkflowRecord, WorkflowVersionRecord };
