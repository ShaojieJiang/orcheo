import {
  SAMPLE_WORKFLOWS,
  type Workflow,
  type WorkflowEdge,
  type WorkflowNode,
} from "@features/workflow/data/workflow-data";
import {
  computeWorkflowDiff,
  type WorkflowDiffResult,
  type WorkflowSnapshot,
} from "./workflow-diff";

const STORAGE_KEY = "orcheo.canvas.workflows.v1";
export const WORKFLOW_STORAGE_EVENT = "orcheo:workflows-updated";
const HISTORY_LIMIT = 20;

const DEFAULT_OWNER = SAMPLE_WORKFLOWS[0]?.owner ?? {
  id: "user-1",
  name: "Avery Chen",
  avatar: "https://avatar.vercel.sh/avery",
};

export interface WorkflowVersionRecord {
  id: string;
  version: string;
  timestamp: string;
  message: string;
  author: Workflow["owner"];
  summary: WorkflowDiffResult["summary"];
  snapshot: WorkflowSnapshot;
}

export interface StoredWorkflow extends Workflow {
  versions: WorkflowVersionRecord[];
}

interface SaveWorkflowInput {
  id?: string;
  name: string;
  description?: string;
  tags?: string[];
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

interface SaveWorkflowOptions {
  versionMessage?: string;
}

interface CreateWorkflowInput {
  name: string;
  description?: string;
  tags?: string[];
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
}

const getStorage = () => {
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage;
  }
  const memoryStore = new Map<string, string>();
  return {
    getItem: (key: string) => memoryStore.get(key) ?? null,
    setItem: (key: string, value: string) => {
      memoryStore.set(key, value);
    },
    removeItem: (key: string) => {
      memoryStore.delete(key);
    },
  } satisfies Pick<Storage, "getItem" | "setItem" | "removeItem">;
};

const storage = getStorage();

const emitUpdate = () => {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(WORKFLOW_STORAGE_EVENT));
};

const readStorage = (): StoredWorkflow[] => {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as StoredWorkflow[];
    return parsed.map((workflow) => ({
      ...workflow,
      versions: workflow.versions ?? [],
      nodes: workflow.nodes ?? [],
      edges: workflow.edges ?? [],
    }));
  } catch (error) {
    console.warn("Failed to read workflow storage", error);
    return [];
  }
};

const writeStorage = (workflows: StoredWorkflow[]) => {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(workflows));
    emitUpdate();
  } catch (error) {
    console.error("Failed to persist workflows", error);
  }
};

const generateWorkflowId = () => {
  if (
    typeof globalThis.crypto !== "undefined" &&
    "randomUUID" in globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return `workflow-${globalThis.crypto.randomUUID()}`;
  }

  const timestamp = Date.now().toString(36);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `workflow-${timestamp}-${randomSuffix}`;
};

const createVersionRecord = (
  workflow: StoredWorkflow,
  snapshot: WorkflowSnapshot,
  diff: WorkflowDiffResult,
  options?: SaveWorkflowOptions,
): WorkflowVersionRecord => {
  const versionNumber = (workflow.versions?.length ?? 0) + 1;
  const timestamp = new Date().toISOString();
  const paddedVersion = versionNumber.toString().padStart(2, "0");

  return {
    id: `${workflow.id}-v${paddedVersion}`,
    version: `v${paddedVersion}`,
    timestamp,
    message:
      options?.versionMessage ??
      `Saved on ${new Date(timestamp).toLocaleString()}`,
    author: workflow.owner ?? DEFAULT_OWNER,
    summary: diff.summary,
    snapshot,
  };
};

export const listWorkflows = (): StoredWorkflow[] => {
  return readStorage();
};

export const getWorkflowById = (
  workflowId: string,
): StoredWorkflow | undefined => {
  return readStorage().find((workflow) => workflow.id === workflowId);
};

export const createWorkflow = (input: CreateWorkflowInput): StoredWorkflow => {
  const workflows = readStorage();
  const now = new Date().toISOString();
  const workflow: StoredWorkflow = {
    id: generateWorkflowId(),
    name: input.name,
    description: input.description,
    createdAt: now,
    updatedAt: now,
    owner: DEFAULT_OWNER,
    tags: input.tags ?? ["draft"],
    nodes: input.nodes ?? [],
    edges: input.edges ?? [],
    versions: [],
  };

  writeStorage([...workflows, workflow]);
  return workflow;
};

export const saveWorkflow = (
  input: SaveWorkflowInput,
  options?: SaveWorkflowOptions,
): StoredWorkflow => {
  const workflows = readStorage();
  const now = new Date().toISOString();
  const existingIndex = input.id
    ? workflows.findIndex((workflow) => workflow.id === input.id)
    : -1;

  let workflow: StoredWorkflow;
  if (existingIndex >= 0) {
    workflow = { ...workflows[existingIndex] };
  } else {
    workflow = {
      id: input.id ?? generateWorkflowId(),
      name: input.name,
      description: input.description,
      createdAt: now,
      updatedAt: now,
      owner: DEFAULT_OWNER,
      tags: input.tags ?? ["draft"],
      nodes: [],
      edges: [],
      versions: [],
    };
  }

  const previousSnapshot: WorkflowSnapshot = {
    name: workflow.name,
    description: workflow.description,
    nodes: workflow.nodes ?? [],
    edges: workflow.edges ?? [],
  };

  workflow.name = input.name;
  workflow.description = input.description;
  workflow.tags = input.tags ?? workflow.tags ?? [];
  workflow.nodes = input.nodes;
  workflow.edges = input.edges;
  workflow.updatedAt = now;

  const snapshot: WorkflowSnapshot = {
    name: workflow.name,
    description: workflow.description,
    nodes: workflow.nodes,
    edges: workflow.edges,
  };

  const diff = computeWorkflowDiff(previousSnapshot, snapshot);

  if (diff.entries.length > 0 || workflow.versions.length === 0) {
    const version = createVersionRecord(workflow, snapshot, diff, options);
    workflow.versions = [...workflow.versions, version].slice(-HISTORY_LIMIT);
  }

  const updatedWorkflows = [...workflows];
  if (existingIndex >= 0) {
    updatedWorkflows[existingIndex] = workflow;
  } else {
    updatedWorkflows.push(workflow);
  }

  writeStorage(updatedWorkflows);
  return workflow;
};

export const createWorkflowFromTemplate = (
  templateId: string,
  overrides?: Partial<CreateWorkflowInput>,
): StoredWorkflow | undefined => {
  const template = SAMPLE_WORKFLOWS.find(
    (workflow) => workflow.id === templateId,
  );
  if (!template) {
    return undefined;
  }

  return createWorkflow({
    name: overrides?.name ?? `${template.name} Copy`,
    description: overrides?.description ?? template.description,
    tags: overrides?.tags ?? template.tags.filter((tag) => tag !== "template"),
    nodes: template.nodes.map((node) => ({
      ...node,
      id: node.id,
    })),
    edges: template.edges.map((edge) => ({
      ...edge,
      id: edge.id,
    })),
  });
};

export const duplicateWorkflow = (
  workflowId: string,
): StoredWorkflow | undefined => {
  const workflow = getWorkflowById(workflowId);
  if (!workflow) {
    return undefined;
  }
  return createWorkflow({
    name: `${workflow.name} Copy`,
    description: workflow.description,
    tags: workflow.tags,
    nodes: workflow.nodes.map((node) => ({ ...node })),
    edges: workflow.edges.map((edge) => ({ ...edge })),
  });
};

export const getVersionSnapshot = (
  workflowId: string,
  versionId: string,
): WorkflowSnapshot | undefined => {
  const workflow = getWorkflowById(workflowId);
  if (!workflow) {
    return undefined;
  }
  const version = workflow.versions.find((entry) => entry.id === versionId);
  return version?.snapshot;
};

export const deleteWorkflow = (workflowId: string) => {
  const workflows = readStorage();
  const filtered = workflows.filter((workflow) => workflow.id !== workflowId);
  if (filtered.length !== workflows.length) {
    writeStorage(filtered);
  }
};

export const clearWorkflowStorage = () => {
  storage.removeItem(STORAGE_KEY);
  emitUpdate();
};
