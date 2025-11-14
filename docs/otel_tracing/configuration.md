# OpenTelemetry Configuration & Trace Tab Operations

This guide explains how to configure OpenTelemetry (OTel) for Orcheo, deploy a collector,
and operate the Workflow Trace tab in Canvas. It complements the architectural notes in
[design.md](design.md) and the implementation milestones recorded in [plan.md](plan.md).

## Runtime configuration

The backend reads tracing settings from environment variables using the `ORCHEO_`
prefix. Defaults are defined in `src/orcheo/config/defaults.py` and validated by
`AppSettings`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_TRACING_EXPORTER` | `none` | Chooses the exporter: `none` disables tracing, `console` writes spans to stdout, and `otlp` emits spans via the OTLP/HTTP protocol. |
| `ORCHEO_TRACING_ENDPOINT` | _none_ | Custom collector endpoint. For OTLP/HTTP exporters the value should include the `/v1/traces` suffix, e.g. `https://collector:4318/v1/traces`. |
| `ORCHEO_TRACING_SERVICE_NAME` | `orcheo-backend` | Resource attribute attached to all spans. Set this to the deployment identifier (e.g. `orcheo-staging`). |
| `ORCHEO_TRACING_SAMPLE_RATIO` | `1.0` | Probability (0.0–1.0) used by `TraceIdRatioBased` sampling. Lower the value to reduce volume in production. |
| `ORCHEO_TRACING_INSECURE` | `false` | When `true`, disables TLS verification for OTLP exporters—useful for local collectors. Leave `false` in production. |
| `ORCHEO_TRACING_HIGH_TOKEN_THRESHOLD` | `1000` | Token count above which `token.chunk` span events are emitted. Increase to reduce noise for long responses. |
| `ORCHEO_TRACING_PREVIEW_MAX_LENGTH` | `512` | Maximum characters kept when prompts, responses, or error messages are attached to span events. |

When using the OTLP exporter, ensure the optional dependency is installed alongside the
backend:

```bash
uv pip install opentelemetry-exporter-otlp
```

Restart the backend after adjusting environment variables so the tracer provider can be
reconfigured.

## Deployment considerations

- **Collector placement** – Keep the collector near the backend to limit latency. The
  default OTLP exporter uses HTTP; expose port `4318` (HTTP) or configure gRPC by
  installing the gRPC exporter.
- **Authentication** – Fronted collectors (e.g., Tempo, Honeycomb) often require API
  tokens. Inject them via environment variables supported by the collector or a reverse
  proxy rather than patching Orcheo code.
- **Sampling strategy** – Tune `ORCHEO_TRACING_SAMPLE_RATIO` for production. Consider
  `0.1` (10%) for initial rollout and adjust based on retention costs.
- **PII controls** – Prompts and responses are truncated and redacted automatically, but
  disable tracing (`ORCHEO_TRACING_EXPORTER=none`) in environments where even partial
  prompts are disallowed.
- **Version skew** – Ensure Canvas and backend deployments are upgraded together. The
  Trace tab expects the Phase 3 API shape and the realtime payload extensions introduced
  in Phase 2.

## Trace tab usage

1. Execute a workflow run from Canvas or the CLI.
2. Select the run in the Execution sidebar; Canvas automatically opens the `Trace` tab
   once trace data is available.
3. Expand nodes in the span tree to inspect prompts, responses, token counts, and
   artifact links. High token usage emits highlighted events using the configured
   threshold.
4. Use the metrics summary to verify end-to-end latency and token totals.
5. Download artifacts or follow external dashboard links (if configured) directly from
   the detail panel.

The Trace tab streams updates for active runs via WebSocket messages. Closed runs load
from the `/executions/{execution_id}/trace` endpoint and respect collector pagination.

## Sample collector configuration

The following minimal configuration works for the OpenTelemetry Collector receiving data
from Orcheo and exporting it to Jaeger. Save as `otel-collector.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
exporters:
  jaeger:
    endpoint: jaeger:14250
    insecure: true
processors:
  batch: {}
pipelines:
  traces:
    receivers: [otlp]
    processors: [batch]
    exporters: [jaeger]
```

Start the collector with:

```bash
otelcol --config otel-collector.yaml
```

Point Orcheo at the collector by setting
`ORCHEO_TRACING_EXPORTER=otlp` and `ORCHEO_TRACING_ENDPOINT=http://collector:4318/v1/traces`.

## Troubleshooting

- **No spans appear** – Verify `ORCHEO_TRACING_EXPORTER` is not `none` and that the
  sample ratio is greater than zero. Check backend logs for exporter initialization
  errors.
- **Startup error about missing OTLP exporter** – Install
  `opentelemetry-exporter-otlp`. The backend raises a runtime error when the exporter is
  requested but not available.
- **TLS handshake failures** – Set `ORCHEO_TRACING_INSECURE=true` for local collectors
  without certificates. For production, use a certificate issued to the collector host or
  terminate TLS before traffic reaches the collector.
- **Trace tab stuck in loading state** – Confirm the backend is reachable at
  `/executions/{id}/trace` and that realtime WebSocket connections are permitted through
  firewalls or proxies.
- **Prompt/response content truncated** – Increase
  `ORCHEO_TRACING_PREVIEW_MAX_LENGTH` to retain more characters at the expense of larger
  span payloads.

With the configuration above, Orcheo emits spans to your observability stack and Canvas
renders them live in the Trace tab.
