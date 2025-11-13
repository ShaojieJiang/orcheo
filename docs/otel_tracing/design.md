# Workflow Tracing Design

## Architectural Overview
The tracing feature spans backend instrumentation, storage, API surfacing, and frontend rendering. We adopt OpenTelemetry for span generation and rely on an external collector/trace store (e.g., Tempo, Jaeger, Honeycomb) to persist data. The Orcheo backend captures trace IDs and exposes a read-optimized view of traces for the Canvas UI while also allowing operators to pivot into external dashboards.

```
Workflow Run -> Execution Engine -> OpenTelemetry SDK -> Collector -> Trace Store
                                      |                         |
                                      +--> Trace Metadata Store +--> Canvas Trace API
```

## Components
### Backend Instrumentation
- **Execution root span**: created when a workflow run starts, tagged with workflow ID, version, trigger, and user context.
- **Node spans**: each node execution emits a child span with step metadata, prompt/response payloads, token usage, artifacts, and status.
- **Error handling**: exceptions mark spans as errored with stack traces and remediation hints.
- **Attributes & events**: prompts/responses stored as span events, token metrics as attributes; artifacts include download URLs and metadata references.
- **Configuration**: instrumentation is optional, activated via environment variables that specify collector endpoint, service name, and sampling policy.

### Trace Metadata Persistence
- Store the execution-to-trace-ID mapping and a minimal cache of span summaries (IDs, names, start/end time, status) in the history repository.
- Persisted metadata enables quick lookup of trace identifiers without querying the external collector for every request.
- Schema changes extend `workflow_execution` records with `trace_id`, plus a `workflow_trace_summary` table for optional caching.

### Trace Retrieval API
- New FastAPI route: `GET /executions/{execution_id}/trace`.
- Controller flow:
  1. Authorize caller using existing execution permissions.
  2. Resolve trace ID from metadata store.
  3. Fetch detailed spans from collector or cache (initial MVP may proxy collector API or use OTLP HTTP).
  4. Normalize spans into hierarchical JSON (parent/child relationships, attributes, events, artifact links).
  5. Return metadata along with auxiliary URLs for dashboards.
- Response example:
```json
{
  "execution_id": "exec_123",
  "trace_id": "abc123",
  "root": {
    "name": "Workflow Run",
    "status": "OK",
    "duration_ms": 12780,
    "children": [
      {
        "name": "Node: Draft Email",
        "status": "OK",
        "duration_ms": 4500,
        "token_usage": {"prompt": 1234, "completion": 678},
        "prompts": [...],
        "responses": [...],
        "artifacts": [{"name": "email.txt", "url": "..."}],
        "children": []
      }
    ]
  },
  "dashboards": {
    "tempo": "https://tempo.example.com/trace/abc123"
  }
}
```

### Canvas Frontend
- **Tab integration**: add a `Trace` tab to the existing tab group, coexisting with Editor, Execution, Readiness, and Settings.
- **State management**: extend `useCanvasUiState` to track the selected tab and active execution; introduce a trace slice that caches traces per execution ID.
- **Data fetching**: new React Query hook `useWorkflowTrace(executionId)` calls the trace endpoint, handles loading/error states, and refetches when executions change.
- **Rendering**: implement a tree/timeline viewer with collapsible span nodes, color-coded status badges, token charts, and artifact buttons. Consider virtualized list for performance.
- **Prompts & responses**: display within expandable sections, with copy-to-clipboard actions and redaction warnings.
- **Artifacts**: link to existing artifact download handlers or provide direct downloads if available.
- **Dashboard links**: show optional buttons to open external observability dashboards.

### Monitoring & Telemetry
- Expose metrics for trace emission success/failure, collector availability, and API latency via Prometheus endpoints.
- Log sampling decisions to help operators tune configuration.
- Provide health checks that detect when tracing is configured but not functioning.

## Alternatives Considered
1. **Persist full trace data in Orcheo DB**: rejected due to storage/maintenance burden and duplication of existing tracing backends.
2. **Frontend-only integration with external dashboards**: rejected because users need in-app visibility without leaving Canvas.
3. **Custom tracing implementation**: rejected in favor of OpenTelemetry standardization and ecosystem tooling.

## Open Questions
- Which collector/storage backend will the initial deployment target (Tempo vs. Jaeger vs. Honeycomb)?
- Do we require sampling strategies beyond head sampling (e.g., tail-based)?
- How should we redact or filter sensitive prompt content dynamically per tenant?
- What retention SLA is acceptable for trace summaries cached in Orcheo storage?

## Future Enhancements
- Integrate trace search/filtering UI for historical executions.
- Correlate traces with metrics and logs within a unified observability dashboard.
- Add streaming updates so traces update live during execution.
- Provide export functionality (e.g., JSON, CSV) for compliance audits.
