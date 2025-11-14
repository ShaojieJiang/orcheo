# Trace Tab Release Notes & Rollout Checklist

This document captures the user-facing release notes for the Trace tab along
with the steps required to enable OpenTelemetry tracing safely in staging and
production.

## Release notes

- Introduces a **Trace** tab on the workflow Canvas that streams OpenTelemetry
  spans for each execution.
- Displays token usage summaries, prompt/response previews, span events, and
  downloadable artifact references.
- Adds backend configuration to select OTLP exporters, sampling ratios, and
  preview limits via `ORCHEO_TRACING_*` environment variables.
- Ships WebSocket updates so operators can debug long-running workflows without
  polling.

## Rollout checklist

### Staging

1. Deploy the latest backend build with tracing instrumentation.
2. Provision or reuse an OTLP collector; update `ORCHEO_TRACING_EXPORTER=otlp`
   and `ORCHEO_TRACING_ENDPOINT` in staging secrets.
3. Set `ORCHEO_TRACING_SERVICE_NAME=orcheo-staging` for easier filtering.
4. Validate collector connectivity by running a workflow and confirming spans in
   the Trace tab and downstream backend (Tempo/Jaeger/etc.).
5. Exercise the Canvas UI and ensure WebSocket updates flow in corporate network
   conditions.
6. Capture screenshots and update runbooks if the Trace tab behavior differs
   from expectations.

### Production

1. Mirror the staging configuration while adjusting secrets/hostnames for
   production collectors.
2. Decide on an initial `ORCHEO_TRACING_SAMPLE_RATIO` based on production RPS; a
   conservative starting point is `0.25`.
3. Enable feature flags or config toggles that expose the Trace tab to end users
   (if using a gradual rollout strategy).
4. Monitor collector telemetry (queue size, error rates) and Canvas performance
   during the first 24 hours. Increase resources if spans backlog.
5. Communicate availability to stakeholders and document escalation contacts for
   tracing-related incidents.
6. Schedule a follow-up review after one week to adjust sampling, retention, or
   UI thresholds based on observed usage.
