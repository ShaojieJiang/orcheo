import type { Edge as CanvasEdge, Node as CanvasNode } from "@xyflow/react";
import {
  type Workflow,
  type WorkflowEdge,
  type WorkflowNode,
} from "@features/workflow/data/workflow-data";
import type { WorkflowDiffResult, WorkflowSnapshot } from "./workflow-diff";
import {
  DEFAULT_OWNER,
  DEFAULT_SUMMARY,
  HISTORY_LIMIT,
} from "./workflow-storage.constants";
import type {
  ApiWorkflow,
  ApiWorkflowVersion,
  CanvasVersionMetadata,
  StoredWorkflow,
  WorkflowVersionRecord,
} from "./workflow-storage.types";

export const ensureArray = <T>(value: T[] | undefined): T[] =>
  Array.isArray(value) ? value : [];

export const cloneNodes = (nodes: WorkflowNode[]): WorkflowNode[] =>
  nodes.map((node) => ({
    ...node,
    position: { ...node.position },
    data: { ...node.data },
  }));

export const cloneEdges = (edges: WorkflowEdge[]): WorkflowEdge[] =>
  edges.map((edge) => ({ ...edge }));

export const emptySnapshot = (
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

export const toCanvasNodes = (nodes: WorkflowNode[]): CanvasNode[] =>
  nodes.map(
    (node) =>
      ({
        id: node.id,
        type: node.type,
        position: node.position,
        data: node.data,
      }) satisfies CanvasNode,
  );

export const toCanvasEdges = (edges: WorkflowEdge[]): CanvasEdge[] =>
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

export const toStoredWorkflow = (
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
