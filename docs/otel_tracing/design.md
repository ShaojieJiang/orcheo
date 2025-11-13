# Workflow Tracing Design

## Architecture Overview
The tracing capability spans backend instrumentation, persistence, APIs, and frontend presentation. Workflow executions emit OpenTelemetry spans that are exported to both an external collector and the Orcheo backend for retrieval. The Canvas app consumes a new trace endpoint and renders a Trace tab dedicated to the active workflow run.

```
Workflow Runner ──▶ OTel SDK ──▶ Collector (optional)
      │                         │
      └─▶ Trace Persistence Service ──▶ Database (spans + metadata)
                                       │
Frontend Canvas ◀─ Trace API ◀──────────┘
```

## Backend Components
1. **OpenTelemetry Initialization**
   - Add OpenTelemetry SDK dependencies to the backend environment.
   - Configure a tracer provider with batch span processor(s) targeting: (a) an OTLP exporter for external collectors, and (b) an in-process exporter that stores span data for Orcheo persistence.
   - Support configuration via environment variables (collector endpoint, sampling ratio, feature flags).

2. **Execution Instrumentation**
   - Start a root span (`workflow.execution`) when a workflow run begins, attaching workflow/run identifiers.
   - Create child spans for each node execution (`workflow.node`), tool invocation (`workflow.tool`), and external call as needed.
   - Annotate spans with attributes: status, latency, input/output hashes, prompt text, response text, token counts, retry metadata, artifact references, and monitoring links.
   - Emit events for errors and retries; propagate trace context through async tasks and WebSocket notifications.

3. **Trace Persistence Layer**
   - Extend existing run history models with trace metadata (trace ID, span counts, artifact IDs).
   - Introduce a `trace_spans` table storing span hierarchy, timing, attributes, and references. The initial schema will include
     columns for `span_id`, `parent_span_id`, `execution_id`, `node_id`, `name`, `status`, `start_time`, `end_time`, `duration_ms`,
     `attributes` (JSONB), and `events` (JSONB). Large prompt/response payloads will continue to live in the artifact store and
     be referenced by ID.
   - Provide repository methods to persist spans as they complete, using bulk upserts for efficiency.
   - Implement retention policies (e.g., configurable TTL) and pruning jobs. Detailed migration steps are outlined in
     [Phase 1 of the implementation plan](./plan.md#phase-1--foundations-week-1).

4. **Trace Retrieval API**
   - Add FastAPI routes under `/executions/{execution_id}/trace` returning span trees.
   - Support query parameters for pagination (e.g., `?cursor=`) and filtering (node IDs, status).
   - Serialize spans into a normalized DTO: span metadata, children list, prompt/response payloads, token usage, artifact links, monitoring URLs.
   - Enforce authentication/authorization; reuse existing run permission checks.

5. **Telemetry & Error Handling**
   - Emit metrics for trace emission success/failure, API latencies, and data volume.
   - Ensure workflows proceed if tracing fails; log warnings and degrade gracefully by disabling further span exports for the
     impacted execution, surfacing a banner in the Trace tab, and falling back to execution history data.

## Frontend Components
1. **State Management**
   - Extend or introduce Canvas state primitives (e.g., `useCanvasUiState`, selectors, controllers) to track the selected Trace
     tab and active execution ID. If equivalent hooks do not exist, create dedicated Trace tab state modules as part of
     implementation.
   - Add a trace data cache keyed by execution ID to avoid redundant fetches.

2. **Data Access**
   - Create a client helper (e.g., `loadWorkflowTrace`) that calls the new trace endpoint, maps DTOs to view models, and normalizes prompt/response/token data.
   - Implement retry logic and loading/error states consistent with existing execution tab behavior.

3. **Trace Tab UI**
   - Add a new `TabsTrigger` and `TabsContent` for `trace` in the workflow layout.
   - Build a `TraceTabContent` component presenting:
     - **Timeline view**: hierarchical span list with expand/collapse, duration bars, status indicators.
     - **Detail panel**: prompt/response text, token metrics (input/output/total), retry info.
     - **Artifacts section**: buttons/links to download associated files.
     - **Monitoring panel**: external dashboard link(s) surfaced when provided.
   - Provide responsive design and accessible semantics (ARIA roles, keyboard navigation).

4. **Interactions**
   - Sync trace selection with execution list; when a user selects a run, fetch traces and focus the corresponding root span.
   - Allow filtering by status (success/failure) and searching by node name.
   - Offer copy-to-clipboard for trace IDs.

5. **Testing & QA**
   - Unit tests for trace serialization, repository operations, and API responses.
   - Frontend unit/integration tests validating tab rendering, data fetching, and timeline interactions.
   - End-to-end scenario covering trace display for a sample workflow.

## Deployment Considerations
- Provide database migrations for new trace tables/columns (aligned with [Phase 1 tasks](./plan.md#phase-1--foundations-week-1)).
- Document environment variables for enabling/disabling tracing and configuring the OTLP endpoint.
- Validate compatibility with existing observability stack; ensure collectors can ingest spans without schema changes.

## Risks & Mitigations
- **Performance Overhead**: Mitigate via sampling, batching, and asynchronous persistence.
- **Storage Growth**: Introduce retention policies and compression for stored spans.
- **Sensitive Data Exposure**: Redact secrets and allow masking configurations for prompts/responses.
- **UI Complexity**: Start with a focused feature set; gather feedback before expanding advanced analytics.
