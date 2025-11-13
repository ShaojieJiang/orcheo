# Workflow Tracing Implementation Plan

## Phase 0 – Foundations (Week 1)
- **Owner**: Backend team lead
- Finalize OpenTelemetry collector selection and deployment topology.
- Document environment variables and secrets required for tracing (collector endpoint, headers, sampling rate).
- Align on data retention policies and redaction rules with security/compliance stakeholders.

## Phase 1 – Backend Instrumentation (Weeks 2–3)
1. **Add dependencies**
   - Update `pyproject.toml` packages (`orcheo`, backend app) with `opentelemetry-sdk`, OTLP exporter, and Prometheus bridge.
   - Ensure `uv.lock` is refreshed and CI passes.
2. **Instrumentation hooks**
   - Wrap workflow execution start in a root span, embed trace context in execution metadata.
   - Emit child spans for each node, capturing prompts, responses, tokens, artifacts.
   - Handle errors with span status and exception details.
3. **Configuration**
   - Introduce environment-driven configuration (enable/disable tracing, sampling rate, collector endpoint).
   - Add startup validation that warns if tracing is enabled but collector is unreachable.
4. **Metadata persistence**
   - Extend execution models, migrations, and repositories with `trace_id` and optional summary cache.
   - Update tests covering persistence and regression checks.

## Phase 2 – Trace Retrieval API (Weeks 3–4)
1. **Collector integration**
   - Build a client module that queries traces by trace ID (initially using OTLP/HTTP or gRPC).
   - Implement exponential backoff and circuit breaker logic for collector downtime.
2. **FastAPI endpoints**
   - Add `GET /executions/{id}/trace` route that authorizes, fetches, normalizes, and returns trace trees.
   - Provide optional query parameters for sampling (e.g., include prompts=false).
   - Cover endpoint with unit and integration tests (fixtures simulate collector responses).
3. **Monitoring**
   - Export metrics for trace fetch latency and failure counts.
   - Update logging to include trace IDs for cross-correlation.

## Phase 3 – Canvas Trace Tab (Weeks 5–6)
1. **UI scaffolding**
   - Add Trace tab trigger/content to workflow layout components.
   - Extend state hooks and controllers to manage trace loading per execution.
2. **Data fetching**
   - Create TypeScript models and API client wrappers for the trace endpoint.
   - Implement React Query hooks with caching, retries, and background refresh.
3. **Visualization**
   - Build `TraceTabContent` component with span tree, status badges, duration bars, token charts, and artifact links.
   - Add prompt/response drawers with copy and redaction indicators.
   - Provide empty/loading/error states consistent with design system.
4. **Testing & QA**
   - Add unit tests for hooks, reducers, and components (Vitest + RTL).
   - Run accessibility checks for the new tab interactions.
   - Capture UX feedback loops with design team.

## Phase 4 – Documentation & Launch (Week 7)
- Update operator docs for configuring tracing, dashboards, and troubleshooting.
- Publish Canvas user guide for the Trace tab, including screenshots and workflows.
- Conduct performance benchmarking (load testing on trace-heavy executions).
- Finalize go/no-go review with stakeholders and schedule beta rollout.

## Milestones & Deliverables
- **M1**: Backend emits spans to collector; trace IDs stored per execution.
- **M2**: Trace API returns normalized span trees for recent executions.
- **M3**: Canvas Trace tab available behind feature flag.
- **M4**: Feature flag removed after QA sign-off; documentation published.

## Risks & Mitigations
- **Collector unavailability**: Provide graceful degradation and retries; keep tracing optional.
- **Payload bloat**: Add configuration to truncate prompts/responses or switch to on-demand fetching.
- **Security concerns**: Enforce access control and redact sensitive data before returning to clients.

## Staffing Estimate
- Backend: 1 senior engineer (6 weeks) + 1 supporting engineer (3 weeks for API/testing).
- Frontend: 1 senior engineer (4 weeks) + design support (1 week) + QA (1 week shared).
- DevOps: 0.5 engineer (2 weeks) for collector deployment and monitoring.
