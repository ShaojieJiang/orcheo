import {
  flattenSpans,
  openTelemetrySpanAdapter,
} from "@evilmartians/agent-prism-data";
import type {
  OpenTelemetryDocument,
  OpenTelemetryEvent,
  OpenTelemetrySpan,
  TraceRecord,
  TraceSpan,
  TraceSpanAttribute,
  TraceSpanAttributeValue,
} from "@evilmartians/agent-prism-types";
import { nanoid } from "nanoid";

import type { BadgeProps } from "@features/workflow/components/trace/agent-prism/Badge";
import type { TraceViewerData } from "@features/workflow/components/trace/agent-prism";

export interface TraceSpanStatusResponse {
  code: "OK" | "ERROR" | "UNSET";
  message?: string | null;
}

export interface TraceSpanEventResponse {
  name: string;
  time?: string | null;
  attributes?: Record<string, unknown>;
}

export interface TraceSpanResponse {
  span_id: string;
  parent_span_id?: string | null;
  name?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  attributes: Record<string, unknown>;
  events?: TraceSpanEventResponse[];
  status?: TraceSpanStatusResponse;
  links?: Array<Record<string, unknown>>;
}

export interface TraceExecutionMetadataResponse {
  id: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  trace_id?: string | null;
  token_usage?: {
    input?: number;
    output?: number;
  };
}

export interface TracePageInfoResponse {
  has_next_page: boolean;
  cursor?: string | null;
}

export interface TraceResponse {
  execution: TraceExecutionMetadataResponse;
  spans: TraceSpanResponse[];
  page_info: TracePageInfoResponse;
}

export interface TraceUpdateMessage {
  type: "trace:update";
  execution_id: string;
  trace_id: string;
  spans: TraceSpanResponse[];
  complete: boolean;
}

export type TraceEntryStatus = "idle" | "loading" | "ready" | "error";

export interface TraceArtifactMetadata {
  id: string;
  downloadUrl?: string;
}

export interface TraceSpanMetadata {
  artifacts: TraceArtifactMetadata[];
  nodeId?: string;
  nodeKind?: string;
  nodeStatus?: string;
  tokenInput?: number;
  tokenOutput?: number;
}

export interface ExecutionTraceEntry {
  executionId: string;
  traceId: string | null;
  metadata?: TraceExecutionMetadataResponse;
  spansById: Record<string, TraceSpanResponse>;
  spanMetadata: Record<string, TraceSpanMetadata>;
  status: TraceEntryStatus;
  error?: string;
  isComplete: boolean;
  lastUpdatedAt?: string;
}

export type ExecutionTraceState = Record<string, ExecutionTraceEntry>;

export interface BuildViewerDataOptions {
  resolveArtifactUrl?: (artifactId: string) => string;
}

const STATUS_CODE_MAP: Record<TraceSpanStatusResponse["code"], string> = {
  OK: "STATUS_CODE_OK",
  ERROR: "STATUS_CODE_ERROR",
  UNSET: "STATUS_CODE_UNSET",
};

const MS_TO_NANO = BigInt(1_000_000);

const ensureDateNano = (value?: string | null): string => {
  if (!value) {
    return "0";
  }
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) {
    return "0";
  }
  return (BigInt(ms) * MS_TO_NANO).toString();
};

const toAttributeValue = (value: unknown): TraceSpanAttributeValue => {
  if (typeof value === "string") {
    return { stringValue: value };
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return { intValue: String(value) };
  }
  if (typeof value === "boolean") {
    return { boolValue: value };
  }
  if (value == null) {
    return { stringValue: "" };
  }
  if (typeof value === "object") {
    return { stringValue: JSON.stringify(value) };
  }
  return { stringValue: String(value) };
};

const toAttributes = (
  attributes: Record<string, unknown>,
): TraceSpanAttribute[] =>
  Object.entries(attributes).map(([key, value]) => ({
    key,
    value: toAttributeValue(value),
  }));

const toEvents = (
  events: TraceSpanEventResponse[] | undefined,
): OpenTelemetryEvent[] | undefined => {
  if (!events?.length) {
    return undefined;
  }
  return events.map((event) => ({
    name: event.name,
    timeUnixNano: ensureDateNano(event.time),
    attributes: event.attributes ? toAttributes(event.attributes) : undefined,
  }));
};

const createSpanMetadata = (span: TraceSpanResponse): TraceSpanMetadata => {
  const artifactsValue = span.attributes?.["orcheo.artifact.ids"];
  const artifacts: TraceArtifactMetadata[] = Array.isArray(artifactsValue)
    ? artifactsValue
        .map((value) => ({ id: String(value) }))
        .filter((item) => item.id.trim().length > 0)
    : [];

  const metadata: TraceSpanMetadata = {
    artifacts,
  };

  const nodeId = span.attributes?.["orcheo.node.id"];
  if (nodeId) {
    metadata.nodeId = String(nodeId);
  }
  const nodeKind = span.attributes?.["orcheo.node.kind"];
  if (nodeKind) {
    metadata.nodeKind = String(nodeKind);
  }
  const nodeStatus = span.attributes?.["orcheo.node.status"];
  if (nodeStatus) {
    metadata.nodeStatus = String(nodeStatus);
  }

  const input = span.attributes?.["orcheo.token.input"];
  const output = span.attributes?.["orcheo.token.output"];
  if (typeof input === "number" && Number.isFinite(input)) {
    metadata.tokenInput = input;
  }
  if (typeof output === "number" && Number.isFinite(output)) {
    metadata.tokenOutput = output;
  }

  return metadata;
};

const mergeAttributes = (
  existing: Record<string, unknown>,
  incoming: Record<string, unknown>,
): Record<string, unknown> => ({
  ...existing,
  ...incoming,
});

const mergeEvents = (
  existing: TraceSpanEventResponse[] | undefined,
  incoming: TraceSpanEventResponse[] | undefined,
): TraceSpanEventResponse[] | undefined => {
  if (!existing?.length) {
    return incoming?.slice();
  }
  if (!incoming?.length) {
    return existing;
  }

  const combined = [...existing];
  const seen = new Set(combined.map((event) => JSON.stringify(event)));
  for (const event of incoming) {
    const key = JSON.stringify(event);
    if (!seen.has(key)) {
      combined.push(event);
      seen.add(key);
    }
  }
  return combined;
};

const mergeSpan = (
  existing: TraceSpanResponse | undefined,
  update: TraceSpanResponse,
): TraceSpanResponse => {
  if (!existing) {
    return { ...update, attributes: { ...update.attributes } };
  }
  return {
    span_id: update.span_id || existing.span_id,
    parent_span_id:
      update.parent_span_id !== undefined
        ? update.parent_span_id
        : existing.parent_span_id,
    name: update.name ?? existing.name,
    start_time: update.start_time ?? existing.start_time,
    end_time: update.end_time ?? existing.end_time,
    attributes: update.attributes
      ? mergeAttributes(existing.attributes, update.attributes)
      : existing.attributes,
    events: mergeEvents(existing.events, update.events),
    status: update.status ?? existing.status,
    links: update.links ?? existing.links,
  };
};

export const createEmptyTraceEntry = (
  executionId: string,
): ExecutionTraceEntry => ({
  executionId,
  traceId: null,
  metadata: undefined,
  spansById: {},
  spanMetadata: {},
  status: "idle",
  error: undefined,
  isComplete: false,
  lastUpdatedAt: undefined,
});

const updateEntryWithSpan = (
  entry: ExecutionTraceEntry,
  span: TraceSpanResponse,
): ExecutionTraceEntry => {
  const merged = mergeSpan(entry.spansById[span.span_id], span);
  return {
    ...entry,
    spansById: {
      ...entry.spansById,
      [merged.span_id]: merged,
    },
    spanMetadata: {
      ...entry.spanMetadata,
      [merged.span_id]: createSpanMetadata(merged),
    },
    lastUpdatedAt: new Date().toISOString(),
  };
};

export const applyTraceResponse = (
  entry: ExecutionTraceEntry,
  response: TraceResponse,
): ExecutionTraceEntry => {
  let next = {
    ...entry,
    status: "ready" as TraceEntryStatus,
    metadata: response.execution,
    traceId: response.execution.trace_id ?? entry.traceId,
    error: undefined,
    isComplete:
      entry.isComplete ||
      Boolean(response.execution.finished_at) ||
      response.page_info.has_next_page === false,
  };

  for (const span of response.spans) {
    next = updateEntryWithSpan(next, span);
  }

  return next;
};

export const applyTraceUpdate = (
  entry: ExecutionTraceEntry,
  update: TraceUpdateMessage,
): ExecutionTraceEntry => {
  let next: ExecutionTraceEntry = {
    ...entry,
    traceId: update.trace_id,
    lastUpdatedAt: new Date().toISOString(),
  };
  for (const span of update.spans) {
    next = updateEntryWithSpan(next, span);
  }
  if (update.complete) {
    next = {
      ...next,
      isComplete: true,
    };
  }
  return next;
};

const toOpenTelemetrySpan = (
  traceId: string,
  span: TraceSpanResponse,
): OpenTelemetrySpan => ({
  traceId,
  spanId: span.span_id,
  parentSpanId: span.parent_span_id ?? undefined,
  name: span.name ?? "span",
  kind: "SPAN_KIND_INTERNAL",
  startTimeUnixNano: ensureDateNano(span.start_time),
  endTimeUnixNano: ensureDateNano(span.end_time ?? span.start_time),
  attributes: toAttributes(span.attributes ?? {}),
  status: {
    code: STATUS_CODE_MAP[span.status?.code ?? "UNSET"],
    message: span.status?.message ?? undefined,
  },
  flags: 0,
  events: toEvents(span.events),
  links: undefined,
});

const buildTraceRecord = (
  entry: ExecutionTraceEntry,
  spans: TraceSpan[],
): TraceRecord => {
  const startedAt = entry.metadata?.started_at
    ? Date.parse(entry.metadata.started_at)
    : undefined;
  const finishedAt = entry.metadata?.finished_at
    ? Date.parse(entry.metadata.finished_at)
    : undefined;
  const durationMs =
    startedAt && finishedAt ? Math.max(finishedAt - startedAt, 0) : 0;
  const totalTokens =
    (entry.metadata?.token_usage?.input ?? 0) +
    (entry.metadata?.token_usage?.output ?? 0);

  return {
    id: entry.executionId,
    name: entry.metadata?.trace_id ?? entry.executionId,
    spansCount: spans.length,
    durationMs,
    agentDescription: entry.metadata?.status ?? "unknown",
    totalTokens,
    startTime: startedAt,
  };
};

const attachMetadataToSpan = (
  span: TraceSpan,
  metadata: Record<string, TraceSpanMetadata>,
  resolver?: (artifactId: string) => string,
): TraceSpan => {
  const meta = metadata[span.id];
  if (meta) {
    span.metadata = {
      ...meta,
      artifacts: meta.artifacts.map((artifact) => {
        if (!resolver) {
          return { id: artifact.id };
        }
        try {
          return {
            id: artifact.id,
            downloadUrl: resolver(artifact.id),
          };
        } catch {
          return { id: artifact.id };
        }
      }),
    };
  }
  if (span.children?.length) {
    span.children = span.children.map((child) =>
      attachMetadataToSpan(child, metadata, resolver),
    );
  }
  return span;
};

const sortChildrenByStart = (span: TraceSpan): TraceSpan => {
  if (span.children?.length) {
    span.children = span.children
      .map((child) => sortChildrenByStart(child))
      .sort((a, b) => a.startTime.getTime() - b.startTime.getTime());
  }
  return span;
};

export const buildTraceViewerData = (
  entry: ExecutionTraceEntry,
  options: BuildViewerDataOptions = {},
): TraceViewerData | undefined => {
  const traceId = entry.traceId ?? entry.metadata?.trace_id;
  if (!traceId) {
    return undefined;
  }
  const spans = Object.values(entry.spansById);
  if (spans.length === 0) {
    return undefined;
  }

  const document: OpenTelemetryDocument = {
    resourceSpans: [
      {
        resource: { attributes: [] },
        scopeSpans: [
          {
            scope: { name: "orcheo.trace" },
            spans: spans.map((span) => toOpenTelemetrySpan(traceId, span)),
          },
        ],
      },
    ],
  };

  const spanTree =
    openTelemetrySpanAdapter.convertRawDocumentsToSpans(document);

  const enrichedTree = spanTree
    .map((span) =>
      attachMetadataToSpan(
        span,
        entry.spanMetadata,
        options.resolveArtifactUrl,
      ),
    )
    .map((span) => sortChildrenByStart(span));

  const flattened = flattenSpans(enrichedTree);
  const traceRecord = buildTraceRecord(entry, flattened);

  const badges: BadgeProps[] = [];
  if (entry.metadata?.status) {
    badges.push({ label: `Status: ${entry.metadata.status}` });
  }
  const inputTokens = entry.metadata?.token_usage?.input ?? 0;
  const outputTokens = entry.metadata?.token_usage?.output ?? 0;
  if (inputTokens || outputTokens) {
    badges.push({
      label: `Tokens in/out: ${inputTokens}/${outputTokens}`,
    });
  }
  if (!entry.isComplete) {
    badges.push({
      label: "Live",
      className:
        "bg-agentprism-warning text-agentprism-warning-muted-foreground",
    });
  }

  return {
    traceRecord,
    spans: enrichedTree,
    badges,
  };
};

export const getEntryStatus = (
  entry: ExecutionTraceEntry | undefined,
): TraceEntryStatus => entry?.status ?? "idle";

export const getEntryError = (
  entry: ExecutionTraceEntry | undefined,
): string | undefined => entry?.error;

export const summarizeTrace = (entry: ExecutionTraceEntry) => {
  const spanCount = Object.keys(entry.spansById).length;
  const totalTokens =
    (entry.metadata?.token_usage?.input ?? 0) +
    (entry.metadata?.token_usage?.output ?? 0);
  return {
    spanCount,
    totalTokens,
  };
};

export const upsertTraceError = (
  entry: ExecutionTraceEntry,
  error: string,
): ExecutionTraceEntry => ({
  ...entry,
  status: "error",
  error,
});

export const markTraceLoading = (
  entry: ExecutionTraceEntry,
): ExecutionTraceEntry => ({
  ...entry,
  status: "loading",
  error: undefined,
});

export const markTraceReady = (
  entry: ExecutionTraceEntry,
): ExecutionTraceEntry => ({
  ...entry,
  status: "ready",
});

export const deriveViewerDataList = (
  state: ExecutionTraceState,
  options: BuildViewerDataOptions = {},
): TraceViewerData[] =>
  Object.values(state)
    .map((entry) => buildTraceViewerData(entry, options))
    .filter((value): value is TraceViewerData => Boolean(value))
    .sort((a, b) => {
      const aStart = a.traceRecord.startTime ?? 0;
      const bStart = b.traceRecord.startTime ?? 0;
      return bStart - aStart;
    });

export const DEFAULT_TRACE_BADGES: BadgeProps[] = [{ label: "Trace" }];

export const ensureTraceId = (): string => nanoid();
