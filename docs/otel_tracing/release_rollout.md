# Trace Tab Release Notes & Rollout Checklist

## Release notes

- **Backend instrumentation** – Workflow executions now emit OpenTelemetry spans for the root run and every node, capturing prompts, responses, token counts, artifacts, and error details. The tracer provider supports console and OTLP exporters with sampling controls. See `src/orcheo/tracing/provider.py` and `src/orcheo/tracing/workflow.py` for implementation specifics.
- **Trace retrieval API** – The backend exposes `/api/executions/{execution_id}/trace`, returning execution metadata, span hierarchies, and pagination data. Live executions push incremental updates over the existing WebSocket channel. Refer to `apps/backend/src/orcheo_backend/app/routers/runs.py` and `apps/backend/src/orcheo_backend/app/trace_utils.py`.
- **Canvas Trace tab** – The Canvas UI adds a Trace tab with tree navigation, search, and span details. Data is sourced via `useExecutionTrace`, which fetches traces, subscribes to realtime updates, and resolves artifact download links. Relevant entry points live in `apps/canvas/src/features/workflow/pages/workflow-canvas/hooks/use-execution-trace.ts` and the trace viewer components under `apps/canvas/src/features/workflow/components/trace/`.

## Rollout checklist

### Staging

- [ ] Enable tracing in the backend environment (e.g., set `ORCHEO_TRACING_EXPORTER=otlp` and point `ORCHEO_TRACING_ENDPOINT` to the staging collector).
- [ ] Deploy or update the staging collector using the sample configuration in [configuration.md](./configuration.md), confirming spans appear in the observability backend.
- [ ] Run smoke workflows and verify trace trees render in Canvas, including live updates and artifact links.
- [ ] Validate performance by monitoring collector and database load while executing high-fanout workflows.
- [ ] Collect feedback from QA on Trace tab usability, accessibility, and error states; address any regressions.

### Production

- [ ] Review staging findings and adjust sampling thresholds or preview lengths as needed for production scale.
- [ ] Coordinate deployment timing with observability owners to ensure the production collector is available and sized appropriately.
- [ ] Roll out backend configuration changes (environment variables and dependency updates) via the standard release pipeline.
- [ ] Announce availability to internal stakeholders, highlighting new monitoring capabilities and links to Tempo/Honeycomb dashboards if applicable.
- [ ] Monitor error budgets and collector health during the first 24 hours; be prepared to fall back to the console exporter or disable tracing if service degradation occurs.
