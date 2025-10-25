import type { Edge as CanvasEdge, Node as CanvasNode } from "@xyflow/react";
import { buildBackendHttpUrl } from "@/lib/config";
import {
  SAMPLE_WORKFLOWS,
  type Workflow,
  type WorkflowEdge,
  type WorkflowNode,
} from "@features/workflow/data/workflow-data";
import { buildGraphConfigFromCanvas } from "./graph-config";
import {
  computeWorkflowDiff,
  type WorkflowDiffResult,
  type WorkflowSnapshot,
} from "./workflow-diff";

interface ApiWorkflow {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  tags: string[];
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

interface ApiWorkflowVersion {
  id: string;
  workflow_id: string;
  version: number;
  graph: Record<string, unknown>;
  metadata: unknown;
  notes: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

interface CanvasVersionMetadata {
  snapshot?: WorkflowSnapshot;
  summary?: WorkflowDiffResult["summary"];
  message?: string;
  canvasToGraph?: Record<string, string>;
  graphToCanvas?: Record<string, string>;
}

interface RequestOptions extends RequestInit {
  expectJson?: boolean;
}

class ApiRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

const DEFAULT_OWNER: Workflow["owner"] = SAMPLE_WORKFLOWS[0]?.owner ?? {
  id: "canvas-owner",
  name: "Canvas Author",
  avatar: "https://avatar.vercel.sh/orcheo",
};

const HISTORY_LIMIT = 20;
const DEFAULT_ACTOR = "canvas-app";
const DEFAULT_SUMMARY: WorkflowDiffResult["summary"] = {
  added: 0,
  removed: 0,
  modified: 0,
};

const API_BASE = "/api/workflows";

const JSON_HEADERS = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

const ensureArray = <T>(value: T[] | undefined): T[] =>
  Array.isArray(value) ? value : [];

const cloneNodes = (nodes: WorkflowNode[]): WorkflowNode[] =>
  nodes.map((node) => ({
    ...node,
    position: { ...node.position },
    data: { ...node.data },
  }));

const cloneEdges = (edges: WorkflowEdge[]): WorkflowEdge[] =>
  edges.map((edge) => ({ ...edge }));

const emptySnapshot = (
  name: string,
  description?: string,
): WorkflowSnapshot => ({
  name,
  description,
  nodes: [],
  edges: [],
});

const toVersionLabel = (version: number): string =>
  `v${version.toString().padStart(2, "0")}`;

const toAuthor = (id: string | undefined): Workflow["owner"] => {
  if (!id) {
    return { ...DEFAULT_OWNER };
  }
  return {
    ...DEFAULT_OWNER,
    id: id || DEFAULT_OWNER.id,
    name: id || DEFAULT_OWNER.name,
  };
};

const toCanvasNodes = (nodes: WorkflowNode[]): CanvasNode[] =>
  nodes.map(
    (node) =>
      ({
        id: node.id,
        type: node.type,
        position: node.position,
        data: node.data,
      }) satisfies CanvasNode,
  );

const toCanvasEdges = (edges: WorkflowEdge[]): CanvasEdge[] =>
  edges.map(
    (edge) =>
      ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
        label: edge.label,
        type: edge.type,
      }) satisfies CanvasEdge,
  );

const readText = async (response: Response): Promise<string> => {
  try {
    return await response.text();
  } catch {
    return "";
  }
};

const request = async <T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> => {
  const expectJson = options.expectJson ?? true;
  const url = buildBackendHttpUrl(path);

  const response = await fetch(url, {
    ...options,
    headers: options.body ? JSON_HEADERS : options.headers,
  });

  if (!response.ok) {
    const detail = (await readText(response)) || response.statusText;
    throw new ApiRequestError(detail, response.status);
  }

  if (!expectJson || response.status === 204) {
    return undefined as T;
  }

  const payload = await readText(response);
  if (!payload) {
    return undefined as T;
  }
  return JSON.parse(payload) as T;
};

const parseCanvasMetadata = (
  metadata: unknown,
  fallbackName: string,
  fallbackDescription?: string,
): CanvasVersionMetadata => {
  if (!metadata || typeof metadata !== "object") {
    return {
      snapshot: emptySnapshot(fallbackName, fallbackDescription),
      summary: { ...DEFAULT_SUMMARY },
    };
  }

  const canvas = (metadata as Record<string, unknown>).canvas;
  if (!canvas || typeof canvas !== "object") {
    return {
      snapshot: emptySnapshot(fallbackName, fallbackDescription),
      summary: { ...DEFAULT_SUMMARY },
    };
  }

  const canvasRecord = canvas as Record<string, unknown>;
  const snapshotPayload = canvasRecord.snapshot as WorkflowSnapshot | undefined;
  const summaryPayload = canvasRecord.summary as
    | WorkflowDiffResult["summary"]
    | undefined;
  const messagePayload = canvasRecord.message as string | undefined;
  const canvasToGraph = canvasRecord.canvasToGraph as
    | Record<string, string>
    | undefined;
  const graphToCanvas = canvasRecord.graphToCanvas as
    | Record<string, string>
    | undefined;

  const snapshot = snapshotPayload
    ? {
        name:
          typeof snapshotPayload.name === "string"
            ? snapshotPayload.name
            : fallbackName,
        description:
          typeof snapshotPayload.description === "string"
            ? snapshotPayload.description
            : fallbackDescription,
        nodes: ensureArray(snapshotPayload.nodes),
        edges: ensureArray(snapshotPayload.edges),
      }
    : emptySnapshot(fallbackName, fallbackDescription);

  const summary = summaryPayload
    ? {
        added: summaryPayload.added ?? 0,
        removed: summaryPayload.removed ?? 0,
        modified: summaryPayload.modified ?? 0,
      }
    : { ...DEFAULT_SUMMARY };

  return {
    snapshot,
    summary,
    message: messagePayload,
    canvasToGraph,
    graphToCanvas,
  };
};

const toVersionRecord = (
  version: ApiWorkflowVersion,
  workflowName: string,
  workflowDescription?: string,
): WorkflowVersionRecord => {
  const metadata = parseCanvasMetadata(
    version.metadata,
    workflowName,
    workflowDescription ?? undefined,
  );

  const message =
    metadata.message ??
    version.notes ??
    `Updated from canvas on ${new Date(version.created_at).toLocaleString()}`;

  return {
    id: version.id,
    version: toVersionLabel(version.version),
    versionNumber: version.version,
    timestamp: version.created_at,
    message,
    author: toAuthor(version.created_by),
    summary: metadata.summary ?? { ...DEFAULT_SUMMARY },
    snapshot:
      metadata.snapshot ?? emptySnapshot(workflowName, workflowDescription),
    graphToCanvas: metadata.graphToCanvas,
  };
};

const toStoredWorkflow = (
  workflow: ApiWorkflow,
  versions: ApiWorkflowVersion[],
): StoredWorkflow => {
  const versionRecords = versions
    .map((entry) =>
      toVersionRecord(entry, workflow.name, workflow.description ?? undefined),
    )
    .slice(-HISTORY_LIMIT);

  const latestSnapshot =
    versionRecords.at(-1)?.snapshot ??
    emptySnapshot(workflow.name, workflow.description ?? undefined);

  return {
    id: workflow.id,
    name: workflow.name,
    description: workflow.description ?? undefined,
    createdAt: workflow.created_at,
    updatedAt: workflow.updated_at,
    owner: toAuthor(undefined),
    tags: ensureArray(workflow.tags),
    nodes: cloneNodes(latestSnapshot.nodes),
    edges: cloneEdges(latestSnapshot.edges),
    versions: versionRecords,
    sourceExample: undefined,
    lastRun: undefined,
    isArchived: workflow.is_archived,
  };
};

const emitUpdate = () => {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(WORKFLOW_STORAGE_EVENT));
};

const fetchWorkflow = async (
  workflowId: string,
): Promise<ApiWorkflow | undefined> => {
  try {
    return await request<ApiWorkflow>(`${API_BASE}/${workflowId}`);
  } catch (error) {
    if (
      error instanceof ApiRequestError &&
      (error.status === 404 || error.status === 410)
    ) {
      return undefined;
    }
    throw error;
  }
};

const fetchWorkflowVersions = async (
  workflowId: string,
): Promise<ApiWorkflowVersion[]> => {
  try {
    return await request<ApiWorkflowVersion[]>(
      `${API_BASE}/${workflowId}/versions`,
    );
  } catch (error) {
    if (
      error instanceof ApiRequestError &&
      (error.status === 404 || error.status === 410)
    ) {
      return [];
    }
    throw error;
  }
};

const upsertWorkflow = async (
  input: SaveWorkflowInput,
  actor: string,
): Promise<string> => {
  if (!input.id) {
    const created = await request<ApiWorkflow>(API_BASE, {
      method: "POST",
      body: JSON.stringify({
        name: input.name,
        description: input.description,
        tags: input.tags ?? [],
        actor,
      }),
    });
    return created.id;
  }

  await request<ApiWorkflow>(`${API_BASE}/${input.id}`, {
    method: "PUT",
    body: JSON.stringify({
      name: input.name,
      description: input.description,
      tags: input.tags ?? [],
      actor,
    }),
  });
  return input.id;
};

const ensureWorkflow = async (
  workflowId: string,
): Promise<StoredWorkflow | undefined> => {
  const [workflow, versions] = await Promise.all([
    fetchWorkflow(workflowId),
    fetchWorkflowVersions(workflowId),
  ]);
  if (!workflow) {
    return undefined;
  }
  return toStoredWorkflow(workflow, versions);
};

const defaultVersionMessage = () =>
  `Updated from canvas on ${new Date().toLocaleString()}`;

export interface WorkflowVersionRecord {
  id: string;
  version: string;
  versionNumber: number;
  timestamp: string;
  message: string;
  author: Workflow["owner"];
  summary: WorkflowDiffResult["summary"];
  snapshot: WorkflowSnapshot;
  graphToCanvas?: Record<string, string>;
}

export interface StoredWorkflow extends Workflow {
  versions: WorkflowVersionRecord[];
  isArchived?: boolean;
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
  actor?: string;
}

const persistVersion = async (
  workflowId: string,
  input: SaveWorkflowInput,
  snapshot: WorkflowSnapshot,
  diff: WorkflowDiffResult,
  actor: string,
  message: string,
) => {
  const canvasNodes = toCanvasNodes(snapshot.nodes);
  const canvasEdges = toCanvasEdges(snapshot.edges);
  const { config, canvasToGraph, graphToCanvas, warnings } =
    await buildGraphConfigFromCanvas(canvasNodes, canvasEdges);

  if (warnings.length > 0) {
    warnings.forEach((warning) => console.warn(warning));
  }

  await request<ApiWorkflowVersion>(`${API_BASE}/${workflowId}/versions`, {
    method: "POST",
    body: JSON.stringify({
      graph: config,
      metadata: {
        canvas: {
          snapshot,
          summary: diff.summary,
          entries: diff.entries,
          message,
          canvasToGraph,
          graphToCanvas,
          tags: input.tags ?? [],
        },
      },
      notes: message,
      created_by: actor,
    }),
  });
};

export const WORKFLOW_STORAGE_EVENT = "orcheo:workflows-updated";

export const listWorkflows = async (): Promise<StoredWorkflow[]> => {
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
  return items.filter((workflow) => workflow.isArchived !== true);
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
  const actor = options?.actor ?? DEFAULT_ACTOR;
  const existing = input.id ? await ensureWorkflow(input.id) : undefined;
  const previousSnapshot =
    existing?.versions.at(-1)?.snapshot ??
    emptySnapshot(existing?.name ?? input.name, existing?.description);

  const currentSnapshot: WorkflowSnapshot = {
    name: input.name,
    description: input.description,
    nodes: cloneNodes(input.nodes),
    edges: cloneEdges(input.edges),
  };

  const diff = computeWorkflowDiff(previousSnapshot, currentSnapshot);
  const needsVersion =
    !existing || existing.versions.length === 0 || diff.entries.length > 0;

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
    );
  }

  const stored = await ensureWorkflow(workflowId);
  if (!stored) {
    throw new Error("Failed to load persisted workflow");
  }

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
  actor: string = DEFAULT_ACTOR,
): Promise<void> => {
  await request<void>(
    `${API_BASE}/${workflowId}?actor=${encodeURIComponent(actor)}`,
    { method: "DELETE", expectJson: false },
  );
  emitUpdate();
};

export const clearWorkflowStorage = () => {
  // No-op placeholder retained for backward compatibility with tests.
};
