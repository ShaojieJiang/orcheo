# OpenTelemetry Configuration & Trace Tab Guide

This guide explains how to configure OpenTelemetry tracing in Orcheo, how the
backend and Canvas UI collaborate to surface workflow traces, and what to do
when instrumentation misbehaves. Combine this document with the
[environment variable reference](../environment_variables.md#tracing-configuration) when rolling out
tracing to new environments.

## Backend configuration

Orcheo loads tracing options from Dynaconf settings and the `ORCHEO_`
environment prefix. The following variables control exporter selection,
networking, and UI thresholds:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_TRACING_EXPORTER` | `none` | Selects the exporter implementation registered by `orcheo.tracing.provider`. Supported values are `none`, `otlp`, and `console`. |
| `ORCHEO_TRACING_ENDPOINT` | _none_ | OTLP endpoint URL (e.g. `https://otel-collector:4318/v1/traces`). Required when `ORCHEO_TRACING_EXPORTER=otlp`. |
| `ORCHEO_TRACING_SERVICE_NAME` | `orcheo-backend` | Service name reported in span resources. Override when running multiple Orcheo clusters. |
| `ORCHEO_TRACING_SAMPLE_RATIO` | `1.0` | Probability (0‑1) that a trace will be recorded. Reduce in high-traffic environments to control cardinality. |
| `ORCHEO_TRACING_INSECURE` | `false` | When `true`, disables TLS verification for the OTLP exporter (useful for local collectors with self-signed certificates). |
| `ORCHEO_TRACING_HIGH_TOKEN_THRESHOLD` | `1000` | Token count that marks span metrics as "high usage" in the Trace tab summary. When a span exceeds this value the backend emits a `token.chunk` event with `reason="high_usage"`, prompting the Trace tab to highlight the span's token totals. |
| `ORCHEO_TRACING_PREVIEW_MAX_LENGTH` | `512` | Maximum number of characters shown for prompt/response previews within span details. |

> **Tip:** For containerized deployments, mount a config map or secret with the
> desired `ORCHEO_TRACING_*` values and pass them to both the backend service
> and asynchronous worker pods.

## Deployment considerations

### Local development

- Set `ORCHEO_TRACING_EXPORTER=console` to log spans to stdout while iterating.
- Alternatively, run a local collector (`docker run otel/opentelemetry-collector`) and
  point `ORCHEO_TRACING_ENDPOINT` to `http://localhost:4318/v1/traces`.
- Leave `ORCHEO_TRACING_SAMPLE_RATIO=1.0` so every workflow execution surfaces in the Trace tab.

### Staging environments

- Use the OTLP exporter with TLS (`https://`) and keep `ORCHEO_TRACING_INSECURE=false`.
- Configure the collector to forward traces to your preferred backend (Tempo, Jaeger, Honeycomb, etc.).
- Start with `ORCHEO_TRACING_SAMPLE_RATIO=0.5` if staging handles load tests; adjust after monitoring storage/ingest costs.

### Production environments

- Define a unique `ORCHEO_TRACING_SERVICE_NAME` per cluster or region for quicker filtering downstream.
- Tune `ORCHEO_TRACING_SAMPLE_RATIO` based on steady-state RPS and trace retention policies (e.g. 0.1 for large clusters).
- Monitor collector queue metrics; increase batch sizes or add sharding if exporters report backpressure.
- Ensure the Trace tab still provides useful previews by keeping `ORCHEO_TRACING_PREVIEW_MAX_LENGTH` ≥ 256.

## Sample OTLP collector configuration

The snippet below wires the Orcheo backend to an OTLP/HTTP collector that
forwards data to Grafana Tempo. Adapt exporters/receivers for your vendor:

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

exporters:
  otlphttp/tempo:
    endpoint: https://tempo.example.com:4318
    headers:
      Authorization: Bearer ${TEMPO_API_TOKEN}

processors:
  batch:
    timeout: 5s
    send_batch_max_size: 1024

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp/tempo]
```

Deploy the collector alongside the backend and set
`ORCHEO_TRACING_ENDPOINT=http://otel-collector:4318/v1/traces`.

## Trace tab usage

1. Open a workflow in the Canvas UI and trigger an execution.
2. Select the **Trace** tab to visualize span hierarchy, token metrics, and
   referenced artifacts in real time.
3. Click a span to inspect prompts, responses, and emitted events. Long values
   are truncated using `ORCHEO_TRACING_PREVIEW_MAX_LENGTH`.
4. Use the metrics summary to identify spans with elevated token usage and
   download attachments when available.

Spans that emit the `token.chunk` event because they crossed
`ORCHEO_TRACING_HIGH_TOKEN_THRESHOLD` appear with a warning badge in the
metrics summary so operators can review them first.

WebSocket updates stream new spans into the tree while a run is in progress; the
final state is cached by the trace retrieval API for historical review.

## Troubleshooting

- **No spans visible:** Confirm `ORCHEO_TRACING_EXPORTER` is not `none` and the
  collector endpoint is reachable from the backend (check for `403`/`503`
  responses in logs).
- **Missing live updates:** Ensure the Canvas client can reach the WebSocket
  endpoint (`/ws/workflows`). Network proxies that strip WebSocket upgrades will
  prevent real-time span delivery.
- **TLS errors:** Set `ORCHEO_TRACING_INSECURE=true` only in non-production
  environments while you install trusted certificates on the collector.
- **High-cardinality storage costs:** Lower `ORCHEO_TRACING_SAMPLE_RATIO` or
  configure rate limiting in the collector's batch processor.
- **Preview truncation feels aggressive:** Increase
  `ORCHEO_TRACING_PREVIEW_MAX_LENGTH` and restart the backend to apply.
