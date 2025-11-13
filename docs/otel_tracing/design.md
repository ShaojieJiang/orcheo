# Workflow Trace Tab Design

## Architecture Overview
The tracing feature spans backend instrumentation, persistence, API exposure, and frontend visualization.

1. **OpenTelemetry Instrumentation**
   - Introduce a trace provider within the backend execution engine to create a root span per workflow execution.
   - Child spans represent node executions; they capture attributes for node ID, display name, status, token usage, latency, and artifact references.
   - Instrumentation uses the OpenTelemetry SDK with configurable exporters (OTLP/HTTP by default) and supports runtime-configurable sampling.

2. **Trace Persistence & Metadata**
   - Extend the run history models to store trace IDs and lightweight span metadata (execution ID, trace ID, latest span timestamp, status).
   - Persist detailed span data via the OpenTelemetry exporter to an external collector; the API fetches data either from the collector or an internal cache, depending on deployment mode.
   - Update repository interfaces to propagate trace identifiers so UI can link to traces immediately after run creation.

3. **Trace Retrieval API**
   - Add REST endpoints under `/executions/{execution_id}/trace` providing:
     - Execution-level metadata: status, started/finished timestamps, total token counts.
     - A hierarchical span tree with attributes, links to artifacts, and optionally correlation IDs to external systems.
     - Pagination or depth limiting for large trace trees.
   - For live runs, integrate with WebSocket channels to push incremental span updates using existing execution channels (augment message schema with trace payloads).

4. **Canvas Trace Tab**
   - Expand Canvas layout to include a `Trace` tab, registered alongside `Editor`, `Execution`, `Readiness`, and `Settings`.
   - Implement a trace viewer component that renders a collapsible tree with duration bars, status badges, token metrics, and artifact actions.
   - Provide a detail panel showing span attributes, prompts/responses, and resource usage.
   - Hook into execution selection state so the Trace tab updates when users switch runs; support loading states and error handling.

5. **External Integrations**
   - Surface optional links to external observability dashboards (e.g., Grafana Tempo, Honeycomb) based on deployment configuration.
   - Allow administrators to configure exporter endpoints and authentication via environment variables or admin UI (documented in configuration guides).

## Data Flow
1. User triggers workflow execution.
2. Backend execution engine starts root span and records trace ID in run metadata.
3. Node executions create child spans, emitting prompts, responses, token usage, and artifact metadata via OpenTelemetry attributes/events.
4. Spans are exported to the configured collector; metadata is persisted in the Orcheo database.
5. Canvas requests `/executions/{id}/trace`; backend aggregates span tree (via collector query or cached span store) and returns JSON payload.
6. Canvas renders trace tree; listens for WebSocket messages to append or update spans for live runs.
7. Users can download artifacts directly from the Trace tab (reusing existing artifact endpoints) and follow links to external dashboards if available.

## Security & Privacy
- Ensure secrets and sensitive content (e.g., API keys) are redacted before being attached to spans.
- Enforce authorization checks on the trace API to match execution access controls.
- Provide configuration flags to disable prompt/response capture for compliance-sensitive environments.

## Performance Considerations
- Use sampling controls to limit trace volume in high-throughput environments.
- Implement pagination or lazy loading for spans when trace depth exceeds configured thresholds.
- Cache recent spans in memory to reduce collector round-trips for live updates.

## Open Questions
- Should artifact blobs be embedded within span events or referenced via URLs only?
- Do we need to support export to multiple tracing backends simultaneously?
- What retention policy should apply to stored trace metadata?
