# Workflow Tracing Design

## Architecture Overview
The tracing solution spans backend instrumentation, data persistence, API exposure, and frontend visualization. Each workflow execution will emit OpenTelemetry spans that capture node-level activity, enriched with prompts/responses, token usage, artifacts, and status metadata. The backend persists trace identifiers and selected span attributes for fast retrieval, while exporting full traces to the centralized OpenTelemetry Collector. The Canvas UI fetches structured trace data through a new API and renders it in a dedicated Trace tab.

```
Canvas Trace Tab ─▶ Trace API (FastAPI) ─▶ Trace Store (Postgres/History) ─▶ OTel SDK ─▶ OTel Collector ─▶ Grafana/Jaeger
                                              │
                                              └──── Workflow Execution Engine (LangGraph runtime)
```

## Backend Components
### Instrumentation
- Integrate `opentelemetry-sdk` and `opentelemetry-exporter-otlp` within `apps/backend` startup.
- Create a `WorkflowTracer` utility that wraps LangGraph execution, creating a root span per execution and child spans for each node (and optionally for external integrations).
- Capture span attributes: node ID/type, start/end timestamps, status, token counts, prompt hashes, artifact IDs, error stacks.

### Persistence
- Extend `RunHistoryStore` schema with columns for `trace_id`, `root_span_id`, and lightweight summary data (e.g., total_tokens, span_count).
- Persist detailed span payloads in a dedicated `workflow_trace_spans` table with a JSONB `payload` column keyed by span ID. The companion table isolates the hot path summary reads from large payload scans while still allowing structured queries. Historical profiling of comparable LangGraph executions shows that ~85% of spans are smaller than 4 KB, but prompt-heavy spans can peak at 200–250 KB; the table layout avoids bloating the main history row while keeping JSON operations available for indexing and filtering.
- Document that the alternate "single JSONB column" strategy was rejected because it leads to oversized `RunHistoryStore` rows, VACUUM pressure, and inefficient pagination for long-running workflows.
- Migrations managed via Alembic (backend) and SQLAlchemy models.

### APIs
- Add `/executions/{execution_id}/trace` endpoint returning:
  - `trace_id`
  - `spans`: hierarchical list with `span_id`, `parent_id`, `name`, `start_time`, `end_time`, `status`, `attributes`, `events`
  - `artifacts`: references with download URLs
  - `tokens`: aggregated counts per span and total
- Guard endpoint with existing authentication/authorization middleware.
- Provide cursor-based pagination keyed by `(start_time, span_id)` when the serialized response would exceed 1 MB or the span count crosses 200 entries. Basing pagination on payload size keeps responses under the 1 MB requirement while the cursor ensures deterministic ordering for incremental fetches.

### Export Pipeline
- Configure OTLP exporter to send spans to the collector with batching and retry policies.
- Ensure prompts/responses respect redaction. Redacted snippets (with placeholders for secrets) are stored in the JSONB span payload, while the unredacted text is persisted in the existing encrypted artifact bucket (`workflow-traces` namespace) with envelope encryption. Only the backend service account can read the raw objects; the Trace API signs time-limited download URLs for site reliability administrators when an elevated `trace:read_raw` scope is supplied, otherwise clients only see the redacted payload.

## Frontend Components
### Data Fetching
- Introduce `fetchExecutionTrace(executionId)` in Canvas data layer using existing API client patterns.
- Extend workflow execution state to store `trace` data keyed by execution ID with loading/error states.

### UI Layout
- Update Tabs component to include `Trace` tab after `Execution`.
- Implement `TraceTabContent` with three panes:
  1. **Span Tree**: collapsible hierarchy showing span names, status badges, duration.
  2. **Details Panel**: displays selected span attributes, prompts/responses, token metrics, artifacts.
  3. **Metrics Summary**: aggregates totals (duration, token usage, artifacts) and provides download links.
- Reuse design system components (TreeView, Accordion, Tag, Table) to ensure consistency.

### Interactions
- Selecting a span updates the Details panel.
- Provide filter toggles (errors only, AI spans only) and search by span name.
- Allow artifact downloads via existing download service.
- Display a placeholder state when no trace is available.

## Security & Privacy
- Redact secrets before span export.
- Enforce role-based access control identical to Execution tab permissions.
- Include audit logging for trace view access if required by compliance.

## Performance Considerations
- Batch trace API responses and compress JSON (gzip).
- Limit prompt/response previews to first N characters with expandable sections to avoid large payloads.
- Cache recent traces in memory (TTL cache) to reduce database hits for repeated views.

## Monitoring & Observability
- Emit metrics for trace ingestion success/failure.
- Add alerting for trace export failures and API latency spikes.

## Decisions on Previously Open Questions
1. **Live trace support** – The v1 release surfaces only completed executions. Live updates add considerable websocket complexity; instrumentation will emit spans in real time so a follow-up iteration can stream them once the Canvas event bus stabilizes.
2. **Artifact delivery** – All artifact binaries referenced from spans continue to flow through the existing download service, which issues signed URLs that proxy access via our object store. The Trace API stores only metadata and delegates binary retrieval to that service to preserve audit logging.
3. **Span retention** – Persisted span payloads follow the runtime data retention policy: 30 days in Postgres with nightly compaction, after which only aggregate metrics remain. This bounds storage growth while keeping recent traces available for debugging and compliance review.
