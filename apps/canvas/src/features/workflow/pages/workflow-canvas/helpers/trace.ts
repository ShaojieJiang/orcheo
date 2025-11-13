import type {
  TraceRecord,
  TraceSpan,
  TraceSpanAttribute,
  TraceSpanCategory,
  TraceSpanStatus as AgentPrismSpanStatus,
} from "@evilmartians/agent-prism-types";

import type { TraceViewerData } from "@/components/agent-prism/TraceViewer/TraceViewer";
import type { BadgeProps } from "@/components/agent-prism/Badge";

export type TraceSpanStatusCode = "OK" | "ERROR" | "UNSET";

export interface TraceSpanEvent {
  name: string;
  time: string | null;
  attributes: Record<string, unknown>;
}

export interface TraceSpanResponse {
  span_id: string;
  parent_span_id: string | null;
  name: string | null;
  start_time: string | null;
  end_time: string | null;
  attributes: Record<string, unknown>;
  events: TraceSpanEvent[];
  status: {
    code: TraceSpanStatusCode;
    message?: string | null;
  };
  links: Record<string, unknown>[];
}

export interface TraceTokenUsage {
  input: number;
  output: number;
}

export interface TraceExecutionMetadata {
  id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  trace_id: string | null;
  token_usage: TraceTokenUsage;
}

export interface TraceResponse {
  execution: TraceExecutionMetadata;
  spans: TraceSpanResponse[];
  page_info: {
    has_next_page: boolean;
    cursor: string | null;
  };
}

export interface TraceUpdateMessage {
  type: "trace:update";
  execution_id: string;
  trace_id: string;
  spans: TraceSpanResponse[];
  complete: boolean;
}

export interface TraceStoreEntry {
  executionId: string;
  traceId: string | null;
  metadata: TraceExecutionMetadata;
  spans: Record<string, TraceSpanResponse>;
  isComplete: boolean;
  lastUpdatedAt: number;
}

export function createFallbackTraceMetadata(
  executionId: string,
  overrides: Partial<TraceExecutionMetadata> = {},
): TraceExecutionMetadata {
  return {
    id: executionId,
    status: overrides.status ?? "running",
    started_at: overrides.started_at ?? null,
    finished_at: overrides.finished_at ?? null,
    trace_id: overrides.trace_id ?? null,
    token_usage: overrides.token_usage ?? { input: 0, output: 0 },
  };
}

const KIND_TO_CATEGORY: Record<string, TraceSpanCategory> = {
  llm: "llm_call",
  llm_call: "llm_call",
  tool: "tool_execution",
  tool_execution: "tool_execution",
  agent: "agent_invocation",
  agent_invocation: "agent_invocation",
  chain: "chain_operation",
  chain_operation: "chain_operation",
  retrieval: "retrieval",
  embedding: "embedding",
  guardrail: "guardrail",
  event: "event",
};

export function initializeTraceStoreEntry(
  metadata: TraceExecutionMetadata,
): TraceStoreEntry {
  return {
    executionId: metadata.id,
    traceId: metadata.trace_id,
    metadata,
    spans: {},
    isComplete: false,
    lastUpdatedAt: Date.now(),
  };
}

export function mergeTraceResponse(
  entry: TraceStoreEntry | undefined,
  response: TraceResponse,
): TraceStoreEntry {
  const base = entry ?? initializeTraceStoreEntry(response.execution);
  const updatedSpans = { ...base.spans };
  response.spans.forEach((span) => {
    updatedSpans[span.span_id] = mergeTraceSpan(
      updatedSpans[span.span_id],
      span,
    );
  });
  return {
    executionId: response.execution.id,
    traceId: response.execution.trace_id,
    metadata: response.execution,
    spans: updatedSpans,
    isComplete: base.isComplete || !response.page_info.has_next_page,
    lastUpdatedAt: Date.now(),
  };
}

export function mergeTraceUpdate(
  entry: TraceStoreEntry,
  update: TraceUpdateMessage,
): TraceStoreEntry {
  const updatedSpans = { ...entry.spans };
  update.spans.forEach((span) => {
    updatedSpans[span.span_id] = mergeTraceSpan(
      updatedSpans[span.span_id],
      span,
    );
  });
  return {
    executionId: entry.executionId,
    traceId: update.trace_id ?? entry.traceId,
    metadata: entry.metadata,
    spans: updatedSpans,
    isComplete: entry.isComplete || update.complete,
    lastUpdatedAt: Date.now(),
  };
}

function mergeTraceSpan(
  existing: TraceSpanResponse | undefined,
  incoming: TraceSpanResponse,
): TraceSpanResponse {
  if (!existing) {
    return normalizeSpan(incoming);
  }

  return normalizeSpan({
    span_id: incoming.span_id,
    parent_span_id: incoming.parent_span_id ?? existing.parent_span_id ?? null,
    name: incoming.name ?? existing.name ?? null,
    start_time: incoming.start_time ?? existing.start_time ?? null,
    end_time: incoming.end_time ?? existing.end_time ?? null,
    attributes: {
      ...existing.attributes,
      ...incoming.attributes,
    },
    events: incoming.events.length > 0 ? incoming.events : existing.events,
    status: incoming.status ?? existing.status,
    links: incoming.links.length > 0 ? incoming.links : existing.links,
  });
}

function normalizeSpan(span: TraceSpanResponse): TraceSpanResponse {
  return {
    ...span,
    parent_span_id: span.parent_span_id ?? null,
    name:
      span.name ??
      span.attributes?.["orcheo.node.display_name"]?.toString?.() ??
      null,
    attributes: span.attributes ?? {},
    events: span.events ?? [],
    status: span.status ?? { code: "UNSET" },
    links: span.links ?? [],
  };
}

export function buildTraceViewerData(entry: TraceStoreEntry): TraceViewerData {
  const spansArray = Object.values(entry.spans);
  const spanNodes = new Map<string, TraceSpan>();
  const parentMap = new Map<string, string | null>();

  spansArray.forEach((span) => {
    const converted = convertSpanToAgentPrism(span, entry.metadata);
    spanNodes.set(converted.id, converted);
    parentMap.set(converted.id, span.parent_span_id ?? null);
  });

  const roots: TraceSpan[] = [];
  spanNodes.forEach((span, id) => {
    const parentId = parentMap.get(id);
    if (parentId && spanNodes.has(parentId)) {
      const parent = spanNodes.get(parentId)!;
      parent.children = parent.children ? [...parent.children, span] : [span];
      parent.children.sort(
        (a, b) => a.startTime.getTime() - b.startTime.getTime(),
      );
    } else {
      roots.push(span);
    }
  });

  roots.sort((a, b) => a.startTime.getTime() - b.startTime.getTime());

  const traceRecord = buildTraceRecord(entry, spansArray);
  const badges = buildTraceBadges(entry);

  return {
    traceRecord,
    spans: roots,
    badges,
  };
}

function buildTraceRecord(
  entry: TraceStoreEntry,
  spans: TraceSpanResponse[],
): TraceRecord {
  const startedAt = parseDate(entry.metadata.started_at);
  const finishedAt = parseDate(entry.metadata.finished_at);
  const durationMs =
    startedAt && finishedAt ? finishedAt.getTime() - startedAt.getTime() : 0;
  const tokens =
    (entry.metadata.token_usage?.input ?? 0) +
    (entry.metadata.token_usage?.output ?? 0);

  return {
    id: entry.traceId ?? entry.executionId,
    name: entry.metadata.id,
    spansCount: spans.length,
    durationMs: durationMs > 0 ? durationMs : 0,
    agentDescription: `Status: ${entry.metadata.status}`,
    totalTokens: tokens > 0 ? tokens : undefined,
    startTime: startedAt?.getTime(),
  };
}

function buildTraceBadges(entry: TraceStoreEntry): BadgeProps[] {
  const badges: BadgeProps[] = [
    {
      label: entry.metadata.status,
      size: "5",
    },
  ];

  const { input = 0, output = 0 } = entry.metadata.token_usage ?? {};
  const total = input + output;
  if (total > 0) {
    badges.push({
      label: `Tokens: ${total.toLocaleString()}`,
      size: "5",
    });
  }

  if (entry.metadata.trace_id) {
    badges.push({
      label: `Trace ID: ${entry.metadata.trace_id.slice(0, 8)}…`,
      size: "5",
      className: "font-mono", // maintain readability
    });
  }

  return badges;
}

function convertSpanToAgentPrism(
  span: TraceSpanResponse,
  metadata: TraceExecutionMetadata,
): TraceSpan {
  const start =
    parseDate(span.start_time) ?? parseDate(metadata.started_at) ?? new Date();
  const end = parseDate(span.end_time) ?? start;
  const duration = Math.max(end.getTime() - start.getTime(), 0);
  const attributes = convertAttributes(span.attributes);
  const tokens = extractTokens(span.attributes);
  const status = mapSpanStatus(span.status, span.end_time);
  const category = inferCategory(span);
  const { input, output } = extractInputOutput(span.events);

  return {
    id: span.span_id,
    title: span.name ?? "span",
    startTime: start,
    endTime: end,
    duration,
    type: category,
    raw: JSON.stringify(span, null, 2),
    attributes,
    status,
    tokensCount: tokens,
    input,
    output,
  };
}

function convertAttributes(
  attributes: Record<string, unknown>,
): TraceSpanAttribute[] {
  return Object.entries(attributes).map(([key, value]) => ({
    key,
    value: normalizeAttributeValue(value),
  }));
}

function normalizeAttributeValue(value: unknown): TraceSpanAttribute["value"] {
  if (typeof value === "string") {
    return { stringValue: value };
  }
  if (typeof value === "number" || typeof value === "bigint") {
    return { intValue: String(value) };
  }
  if (typeof value === "boolean") {
    return { boolValue: value };
  }
  if (value == null) {
    return { stringValue: "" };
  }
  return { stringValue: JSON.stringify(value) };
}

function extractTokens(
  attributes: Record<string, unknown>,
): number | undefined {
  const input = Number(attributes["orcheo.token.input"] ?? 0);
  const output = Number(attributes["orcheo.token.output"] ?? 0);
  const total = input + output;
  return Number.isFinite(total) && total > 0 ? total : undefined;
}

function mapSpanStatus(
  status: TraceSpanResponse["status"],
  endTime: string | null,
): AgentPrismSpanStatus {
  switch (status.code) {
    case "OK":
      return "success";
    case "ERROR":
      return "error";
    default:
      return endTime ? "warning" : "pending";
  }
}

function inferCategory(span: TraceSpanResponse): TraceSpanCategory {
  const rawKind = span.attributes?.["orcheo.node.kind"];
  if (typeof rawKind === "string") {
    const normalized = rawKind.toLowerCase();
    if (KIND_TO_CATEGORY[normalized]) {
      return KIND_TO_CATEGORY[normalized];
    }
  }
  if (!span.parent_span_id) {
    return "agent_invocation";
  }
  return "span";
}

function extractInputOutput(events: TraceSpanEvent[]): {
  input?: string;
  output?: string;
} {
  const result: { input?: string; output?: string } = {};
  for (const event of events) {
    if (event.name === "prompt" && result.input === undefined) {
      result.input = renderEventPreview(event.attributes);
    }
    if (event.name === "response" && result.output === undefined) {
      result.output = renderEventPreview(event.attributes);
    }
  }
  return result;
}

function renderEventPreview(attributes: Record<string, unknown>): string {
  const preview = attributes.preview ?? attributes.text ?? attributes.content;
  if (typeof preview === "string") {
    return preview;
  }
  return JSON.stringify(attributes);
}

function parseDate(value: string | null): Date | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
