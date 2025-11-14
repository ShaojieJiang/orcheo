# OpenTelemetry Configuration & Trace Tab Guide

The tracing feature stitches together backend instrumentation, an OpenTelemetry (OTel) collector, and the Canvas Trace tab. This guide explains how to configure exporters, roll the feature out safely, and make the most of the Trace UI once telemetry is flowing.

## Runtime configuration

Tracing is controlled entirely through environment variables exposed by `AppSettings` and the Dynaconf loader. Values are read from the `ORCHEO_` namespace and fallback to the defaults defined in `src/orcheo/config/defaults.py`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORCHEO_TRACING_EXPORTER` | `none` | Selects the exporter backend. Supported values are `none`, `console`, or `otlp`. The backend automatically configures a `TracerProvider` with batching when tracing is enabled. |
| `ORCHEO_TRACING_ENDPOINT` | _unset_ | Optional OTLP endpoint (HTTP) forwarded to `OTLPSpanExporter`. Leave blank for collectors running on `http://localhost:4318`. |
| `ORCHEO_TRACING_SERVICE_NAME` | `orcheo-backend` | Service resource name published with every span. Useful for multi-service deployments. |
| `ORCHEO_TRACING_SAMPLE_RATIO` | `1.0` | Fraction of traces sampled by the backend sampler. Accepts floats in `[0.0, 1.0]`. |
| `ORCHEO_TRACING_INSECURE` | `false` | When `true`, disables TLS verification on OTLP HTTP exports. Only use for local or trusted collectors. |
| `ORCHEO_TRACING_HIGH_TOKEN_THRESHOLD` | `1000` | Token count above which `token.chunk` span events are emitted. Reducing the value surfaces unusually large prompts/responses sooner. |
| `ORCHEO_TRACING_PREVIEW_MAX_LENGTH` | `512` | Maximum number of characters preserved when prompts/responses are truncated for span previews. |

Update the variables in your deployment manifest (Kubernetes `ConfigMap`, Docker Compose environment, etc.) and restart the backend. No code changes are necessary after toggling these settings.

### Recommended scenarios

- **Local verification** – Set `ORCHEO_TRACING_EXPORTER=console` to log spans directly to stdout. Combine with a low sample ratio to limit noise while validating instrumentation.
- **Staging** – Use OTLP with a short retention window to confirm collector wiring. Example: `ORCHEO_TRACING_EXPORTER=otlp`, `ORCHEO_TRACING_ENDPOINT=https://otel-staging.internal:4318`, `ORCHEO_TRACING_SAMPLE_RATIO=0.5`.
- **Production** – Point at the managed collector/observability backend, keep sampling near 1.0 for critical workflows, and tune thresholds to balance fidelity and storage.

## Sample OpenTelemetry Collector

The backend emits OTLP/HTTP spans. The snippet below shows a minimal collector configuration that receives OTLP data, attaches resource attributes, and forwards traces to Tempo and Honeycomb simultaneously.

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
processors:
  batch: {}
  attributes/add_deployment:
    actions:
      - key: deployment.environment
        value: "staging"
        action: insert
exporters:
  logging:
    verbosity: detailed
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
  otlp/honeycomb:
    endpoint: api.honeycomb.io:443
    headers:
      x-honeycomb-team: ${HONEYCOMB_API_KEY}
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, attributes/add_deployment]
      exporters: [logging, otlp/tempo, otlp/honeycomb]
```

Deploy the collector close to the backend to avoid exporting spans over the public internet. When testing locally, run the collector alongside the backend and point `ORCHEO_TRACING_ENDPOINT` to `http://localhost:4318`.

### Collector performance planning

- **Right-size the deployment** – As a starting point, allocate at least 1 vCPU and 512 MiB of memory per 2,000 spans per second for production workloads. Increase resources when you enable advanced processors such as tail-based sampling or span metrics.
- **Scale horizontally** – When sustained throughput exceeds the limits of a single replica, run the collector behind a load balancer and enable the [OpenTelemetry `k8scluster` receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/k8sclusterreceiver) or another service discovery mechanism to distribute load.
- **Tune batching** – Adjust the `batch` processor settings (`timeout`, `send_batch_size`) to smooth bursty workloads. Longer timeouts reduce CPU usage at the cost of higher latency before spans are exported.

### Secure collector access

- **Require authentication** – Enable mTLS or an authenticating reverse proxy (e.g., Envoy with JWT validation) on the collector ingress when exposing OTLP endpoints beyond a private cluster. Never leave the collector accessible on the public internet without authentication.
- **Restrict network access** – Limit inbound connections to trusted backends using Kubernetes NetworkPolicies, security groups, or firewall rules. Only the Orcheo backend and authorised observability tooling should be allowed to submit spans.
- **Rotate credentials** – If you rely on API keys (for example, when forwarding to third-party vendors), store them in secret managers and rotate them periodically. Monitor for failed authentication attempts to catch misconfigurations early.

### Monitor the collector

- **Enable health checks** – Configure liveness and readiness probes (or Docker health checks) so orchestration platforms can restart unhealthy collectors automatically.
- **Export collector metrics** – Turn on the [`prometheus` exporter](https://opentelemetry.io/docs/collector/configuration/#prometheus) or another metrics backend to track queue depth, exporter errors, and processor load. Alert on sustained error ratios or queue saturation.
- **Log at appropriate levels** – Keep the `logging` exporter at `info` in production to avoid excessive disk usage. Raise the verbosity temporarily during incident response to gather detailed span export diagnostics.

## Troubleshooting

1. **Trace tab stays empty** – Confirm that the backend exporter is enabled (`ORCHEO_TRACING_EXPORTER` not `none`) and that the collector is accepting spans. The backend logs a warning if the exporter fails to initialise or the OTLP dependency is missing.
2. **`RuntimeError: OTLP exporter requested but dependency unavailable`** – Install `opentelemetry-exporter-otlp` in the backend environment or switch to the console exporter temporarily. The backend raises this exception during startup when OTLP support is missing.
3. **TLS handshake failures** – Set `ORCHEO_TRACING_INSECURE=true` for test environments using self-signed certificates, or supply the collector's CA bundle via standard TLS configuration variables.
4. **Missing prompt/response previews** – Increase `ORCHEO_TRACING_PREVIEW_MAX_LENGTH` to preserve longer snippets in span events. Prompts larger than the preview limit are still exported to the collector but truncated in the Orcheo UI.
5. **High-volume workflows overwhelm storage** – Reduce `ORCHEO_TRACING_SAMPLE_RATIO` or raise `ORCHEO_TRACING_HIGH_TOKEN_THRESHOLD` to limit auxiliary span events.

## Using the Trace tab

Once tracing is configured, the Canvas UI automatically surfaces spans under the **Trace** tab on each workflow run:

1. Select a workflow execution from the run history. The Trace tab becomes available next to the existing editor and execution tabs.
2. The client calls `/api/executions/{execution_id}/trace` and streams live updates over the existing WebSocket channel, so traces populate even while a run is still executing.
3. Use the search box to filter spans by name or attribute and the expand/collapse controls to adjust the tree view. Span lists, token usage summaries, and status badges are kept in sync with backend updates.
4. Click any span to view prompts, responses, and artifact links in the details panel. Artifact links resolve through the backend `/api/artifacts/{id}/download` endpoint, letting you inspect model outputs without leaving the page.
5. When issues arise, press **Refresh trace** in the tab header to re-fetch the latest snapshot; the client retries automatically if live updates pause.

Tip: keep the Trace tab open during complex runs—`useExecutionTrace` automatically resubscribes when you change the active execution, so you can flip between runs without losing context.
