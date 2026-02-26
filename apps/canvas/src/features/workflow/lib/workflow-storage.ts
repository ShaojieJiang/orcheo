import { SAMPLE_WORKFLOWS } from "@features/workflow/data/workflow-data";
import { getAccessTokenSubject } from "@features/auth/lib/auth-session";
import { computeWorkflowDiff, type WorkflowSnapshot } from "./workflow-diff";
import {
  DEFAULT_ACTOR,
  WORKFLOW_STORAGE_EVENT,
} from "./workflow-storage.constants";
import {
  cloneEdges,
  cloneNodes,
  emptySnapshot,
  toStoredWorkflow,
} from "./workflow-storage-helpers";
import {
  API_BASE,
  fetchWorkflowVersions,
  request,
  upsertWorkflow,
} from "./workflow-storage-api";
import {
  defaultVersionMessage,
  ensureWorkflow,
  persistVersion,
} from "./workflow-storage-versioning";
import type {
  ApiWorkflow,
  SaveWorkflowInput,
  SaveWorkflowOptions,
  StoredWorkflow,
} from "./workflow-storage.types";

interface ListWorkflowsOptions {
  forceRefresh?: boolean;
}

interface WorkflowListCacheEntry {
  items: StoredWorkflow[];
  cachedAt: number;
}

const WORKFLOW_LIST_CACHE_TTL_MS = 5 * 60 * 1000;
let workflowListCache: WorkflowListCacheEntry | undefined;
let workflowListInflight: Promise<StoredWorkflow[]> | undefined;
let workflowListRequestId = 0;

const resolveActor = (actor?: string): string => {
  const explicitActor = actor?.trim();
  if (explicitActor) {
    return explicitActor;
  }

  return getAccessTokenSubject() ?? DEFAULT_ACTOR;
};

const emitUpdate = () => {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(WORKFLOW_STORAGE_EVENT));
};

export const invalidateWorkflowListCache = () => {
  workflowListCache = undefined;
  workflowListInflight = undefined;
};

export const listWorkflows = async (
  options: ListWorkflowsOptions = {},
): Promise<StoredWorkflow[]> => {
  const forceRefresh = options.forceRefresh ?? false;
  const now = Date.now();
  const cacheAge = workflowListCache ? now - workflowListCache.cachedAt : null;
  const cacheIsFresh =
    cacheAge !== null && cacheAge < WORKFLOW_LIST_CACHE_TTL_MS;

  if (!forceRefresh && cacheIsFresh && workflowListCache) {
    return workflowListCache.items;
  }

  if (!forceRefresh && workflowListInflight) {
    return workflowListInflight;
  }

  workflowListRequestId += 1;
  const requestId = workflowListRequestId;

  const inflightPromise = (async () => {
    const workflows = await request<ApiWorkflow[]>(API_BASE);
    const activeWorkflows = workflows.filter(
      (workflow) => workflow.is_archived !== true,
    );
    const items = await Promise.all(
      activeWorkflows.map(async (workflow) => {
        const versions = await fetchWorkflowVersions(workflow.id);
        return toStoredWorkflow(workflow, versions);
      }),
    );
    const filteredItems = items.filter(
      (workflow) => workflow.isArchived !== true,
    );
    if (requestId === workflowListRequestId) {
      workflowListCache = { items: filteredItems, cachedAt: Date.now() };
    }
    return filteredItems;
  })();

  workflowListInflight = inflightPromise;

  try {
    return await inflightPromise;
  } finally {
    if (workflowListInflight === inflightPromise) {
      workflowListInflight = undefined;
    }
  }
};

export const getWorkflowById = async (
  workflowId: string,
): Promise<StoredWorkflow | undefined> => {
  return ensureWorkflow(workflowId);
};

export const saveWorkflow = async (
  input: SaveWorkflowInput,
  options?: SaveWorkflowOptions,
): Promise<StoredWorkflow> => {
  const actor = resolveActor(options?.actor);
  const existing = input.id ? await ensureWorkflow(input.id) : undefined;
  const previousSnapshot: WorkflowSnapshot =
    existing?.versions.at(-1)?.snapshot ??
    emptySnapshot(existing?.name ?? input.name, existing?.description);

  const currentSnapshot: WorkflowSnapshot = {
    name: input.name,
    description: input.description,
    nodes: cloneNodes(input.nodes),
    edges: cloneEdges(input.edges),
  };

  const diff = computeWorkflowDiff(previousSnapshot, currentSnapshot);
  const latestRunnableConfig =
    existing?.versions.at(-1)?.runnableConfig ?? null;
  const runnableConfigToPersist =
    options?.runnableConfig === undefined
      ? latestRunnableConfig
      : options.runnableConfig;
  const needsVersion =
    !existing ||
    existing.versions.length === 0 ||
    diff.entries.length > 0 ||
    options?.forceVersion === true;

  const workflowId = await upsertWorkflow(input, actor);

  if (needsVersion) {
    const message = options?.versionMessage ?? defaultVersionMessage();
    await persistVersion(
      workflowId,
      input,
      currentSnapshot,
      diff,
      actor,
      message,
      runnableConfigToPersist,
    );
  }

  const stored = await ensureWorkflow(workflowId);
  if (!stored) {
    throw new Error("Failed to load persisted workflow");
  }

  invalidateWorkflowListCache();
  emitUpdate();
  return stored;
};

export const createWorkflow = async (
  input: Omit<SaveWorkflowInput, "id">,
): Promise<StoredWorkflow> => {
  return saveWorkflow(input, { versionMessage: "Initial draft" });
};

export const createWorkflowFromTemplate = async (
  templateId: string,
  overrides?: Partial<Omit<SaveWorkflowInput, "nodes" | "edges">>,
): Promise<StoredWorkflow | undefined> => {
  const template = SAMPLE_WORKFLOWS.find(
    (workflow) => workflow.id === templateId,
  );
  if (!template) {
    return undefined;
  }

  return saveWorkflow({
    name: overrides?.name ?? `${template.name} Copy`,
    description: overrides?.description ?? template.description,
    tags: overrides?.tags ?? template.tags.filter((tag) => tag !== "template"),
    nodes: cloneNodes(template.nodes),
    edges: cloneEdges(template.edges),
  });
};

export const duplicateWorkflow = async (
  workflowId: string,
): Promise<StoredWorkflow | undefined> => {
  const existing = await getWorkflowById(workflowId);
  if (!existing) {
    return undefined;
  }

  const snapshot =
    existing.versions.at(-1)?.snapshot ??
    ({
      name: existing.name,
      description: existing.description,
      nodes: existing.nodes,
      edges: existing.edges,
    } satisfies WorkflowSnapshot);

  return saveWorkflow(
    {
      name: `${existing.name} Copy`,
      description: existing.description,
      tags: existing.tags,
      nodes: cloneNodes(snapshot.nodes),
      edges: cloneEdges(snapshot.edges),
    },
    { versionMessage: `Duplicated from ${existing.name}` },
  );
};

export const getVersionSnapshot = async (
  workflowId: string,
  versionId: string,
): Promise<WorkflowSnapshot | undefined> => {
  const workflow = await getWorkflowById(workflowId);
  return workflow?.versions.find((entry) => entry.id === versionId)?.snapshot;
};

export const deleteWorkflow = async (
  workflowId: string,
  actor?: string,
): Promise<void> => {
  const resolvedActor = resolveActor(actor);
  await request<void>(
    `${API_BASE}/${workflowId}?actor=${encodeURIComponent(resolvedActor)}`,
    { method: "DELETE", expectJson: false },
  );
  invalidateWorkflowListCache();
  emitUpdate();
};

export type {
  StoredWorkflow,
  WorkflowVersionRecord,
  SaveWorkflowInput,
  SaveWorkflowOptions,
} from "./workflow-storage.types";

export { WORKFLOW_STORAGE_EVENT } from "./workflow-storage.constants";
