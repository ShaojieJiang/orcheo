# Workflow Tracing Requirements

## Overview
The observability initiative for Milestone 6 is shifting toward a dedicated tracing experience. We must expose OpenTelemetry trace data for every workflow run and present it inside the Canvas application so operators can inspect execution behavior, prompts, token usage, artifacts, and system health in one place.

## Goals
- Provide a first-class "Trace" tab within the Canvas workflow page that visualizes the trace tree for the active execution.
- Capture per-step prompt/response payloads, token metrics, and generated artifacts as trace span attributes.
- Surface links or embedded previews for artifacts generated during a workflow run.
- Enable operators to diagnose latency, failure points, and infrastructure issues using trace metadata and dashboards.

## In Scope
- Integrating OpenTelemetry instrumentation into workflow execution services to emit spans for workflows and individual nodes.
- Persisting trace identifiers and minimal metadata required to retrieve trace data for a given execution.
- Backend API endpoints or proxies that return trace content tailored for the Canvas experience.
- Canvas UI work to fetch, render, and interact with the trace data, including token and artifact details.
- Documentation updates covering setup, configuration, and user guidance for tracing.

## Out of Scope
- Long-term storage and retention policies beyond the MVP retention window (to be defined later).
- Third-party collector deployment or hosted tracing infrastructure; the MVP targets compatibility with an existing OpenTelemetry collector endpoint provided by operators.
- Retrofitting legacy execution viewers outside the Canvas workflow page.

## Success Criteria
- Users can open the Trace tab for any execution and see a hierarchical view of spans, each annotated with prompts/responses, token counts, durations, and status.
- Artifact downloads or inline previews are accessible from the associated span entries.
- Trace metadata is queryable via API within <300 ms for recent executions.
- Instrumentation is gated behind configuration toggles so environments without OpenTelemetry collectors continue to function without errors.
- Monitoring dashboards (e.g., Grafana/Tempo or similar) can ingest the emitted spans without custom adapters.

## Assumptions
- An OpenTelemetry collector endpoint is available and reachable from backend services.
- Workflow executions already have stable identifiers that can be correlated with trace IDs.
- Frontend teams can extend existing state management patterns to include trace data without rewriting the entire Canvas layout.

## Dependencies
- OpenTelemetry SDK packages for Python backend services.
- Frontend visualization components (potentially third-party timeline/tree libraries) that can render nested spans.
- Backend storage layer capable of persisting additional trace metadata.

## Risks
- High volume of span attributes (prompts, responses, artifacts) increasing payload sizes and impacting performance.
- Instrumentation errors causing execution slowdowns or failures when the collector is unavailable.
- UI complexity leading to confusing trace navigation without careful UX design.

## Compliance & Security Considerations
- Sensitive prompt or response content must be redacted or protected in accordance with data handling policies.
- Trace endpoints must enforce the same authorization scope as execution history APIs.
- Token and artifact data should respect existing audit logging and access controls.
