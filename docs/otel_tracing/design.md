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
- Persist detailed span payloads in a JSONB column or companion table keyed by span ID to enable structured API responses without rehydrating from the collector.
- Migrations managed via Alembic (backend) and SQLAlchemy models.

### APIs
- Add `/executions/{execution_id}/trace` endpoint returning:
  - `trace_id`
  - `spans`: hierarchical list with `span_id`, `parent_id`, `name`, `start_time`, `end_time`, `status`, `attributes`, `events`
  - `artifacts`: references with download URLs
  - `tokens`: aggregated counts per span and total
- Guard endpoint with existing authentication/authorization middleware.
- Provide pagination or chunking for large traces (e.g., >500 spans).

### Export Pipeline
- Configure OTLP exporter to send spans to the collector with batching and retry policies.
- Ensure prompts/responses respect redaction; store redacted versions in span attributes but keep raw text only where secure.

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

## Open Questions
1. Do we need to support live (in-progress) traces, or only completed executions?
2. Should artifact binaries be linked directly or proxied through signed URLs?
3. What retention period is acceptable for stored span payloads in the history database?
