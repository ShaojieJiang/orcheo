# OpenTelemetry Tracing Requirements

## Overview

This document defines the functional and non-functional requirements for implementing OpenTelemetry-based distributed tracing in Orcheo, providing per-workflow execution visibility through a dedicated Trace tab.

**Last Updated:** 2025-11-13
**Status:** Draft
**Related Documents:**
- [Design Document](./design.md)
- [Implementation Plan](./plan.md)
- [Milestone 6 Roadmap](../roadmap.md)

---

## Business Objectives

### Primary Goals
1. Enable developers to understand workflow execution behavior at a granular level
2. Provide visibility into node-level performance and timing characteristics
3. Facilitate debugging of complex multi-node workflows
4. Support performance optimization through detailed execution metrics
5. Build foundation for advanced observability features (metrics, alerts, SLOs)

### Success Criteria
- Users can view complete execution traces for any workflow run
- Trace data includes timing, status, and contextual information for each node
- Trace visualization is intuitive and actionable
- Performance overhead < 10% for instrumented workflows
- Trace data retention configurable (default: 30 days)

---

## Functional Requirements

### FR-1: OpenTelemetry Integration

**FR-1.1: SDK Integration**
- MUST integrate OpenTelemetry SDK for Python in the backend
- MUST support configurable trace providers (OTLP, console, in-memory)
- MUST allow environment-based configuration (dev vs production)
- SHOULD support standard OpenTelemetry environment variables (`OTEL_*`)

**FR-1.2: Span Creation**
- MUST create a root span for each workflow execution
- MUST create child spans for each node execution
- MUST capture span context and propagate through async execution
- SHOULD support custom span attributes for node-specific metadata

**FR-1.3: Span Attributes**
- MUST capture standard attributes:
  - `workflow.id` - Workflow identifier
  - `workflow.name` - Workflow name
  - `execution.id` - Execution identifier
  - `node.id` - Node identifier
  - `node.type` - Node type (AINode, TaskNode, etc.)
  - `node.label` - Human-readable node name
  - `span.kind` - OpenTelemetry span kind (INTERNAL, CLIENT, etc.)
- SHOULD capture optional attributes:
  - `node.input` - Sanitized input data
  - `node.output` - Sanitized output data
  - `error.type` - Error class name (if failed)
  - `error.message` - Error message (if failed)
  - `error.stacktrace` - Stack trace (if failed)

**FR-1.4: Timing Data**
- MUST capture start and end timestamps for all spans
- MUST calculate duration automatically
- SHOULD capture additional timing metrics (queue time, processing time)

### FR-2: Workflow Instrumentation

**FR-2.1: Execution Entry Points**
- MUST instrument workflow execution in `workflow_execution.py`
- MUST create root span at workflow start
- MUST close root span at workflow completion/failure
- MUST handle cancellation and timeout scenarios

**FR-2.2: Node Execution**
- MUST instrument all node types (BaseNode, AINode, TaskNode, DecisionNode)
- MUST create spans around `node.__call__()` or `node.run()` methods
- MUST capture node status (pending, running, completed, failed)
- SHOULD use decorators or context managers for instrumentation

**FR-2.3: Error Handling**
- MUST capture exceptions as span events
- MUST set span status to ERROR when node fails
- MUST record error attributes (type, message, stacktrace)
- SHOULD NOT leak sensitive data in error messages

**FR-2.4: State Transitions**
- MUST emit span events for key state transitions
- SHOULD capture state snapshots at configurable intervals
- SHOULD support correlation with LangGraph checkpoints

### FR-3: Trace Storage

**FR-3.1: Persistence**
- MUST store trace data persistently (SQLite for dev, PostgreSQL for production)
- MUST support querying traces by workflow ID, execution ID, time range
- MUST support filtering spans by node type, status, duration
- SHOULD implement retention policies (configurable, default 30 days)

**FR-3.2: Data Model**
- MUST store spans with OpenTelemetry-compliant schema:
  - `trace_id` (128-bit identifier)
  - `span_id` (64-bit identifier)
  - `parent_span_id` (nullable, for hierarchical structure)
  - `name` (span name)
  - `start_time` (timestamp)
  - `end_time` (timestamp)
  - `attributes` (key-value pairs, JSON)
  - `status` (OK, ERROR, UNSET)
  - `events` (timestamped events within span)
- MUST maintain referential integrity between traces and executions
- SHOULD optimize for read queries (indexed by trace_id, execution_id)

**FR-3.3: Export Support**
- SHOULD support exporting traces in OpenTelemetry Protocol (OTLP) format
- SHOULD support exporting to external observability platforms (Jaeger, Zipkin, DataDog)
- MAY support export to JSON/CSV for offline analysis

### FR-4: API Endpoints

**FR-4.1: Trace Retrieval**
- MUST provide `GET /workflows/{workflow_id}/traces` - List traces for workflow
  - Query params: `limit`, `offset`, `start_date`, `end_date`, `status`
  - Response: Paginated list of trace summaries
- MUST provide `GET /executions/{execution_id}/trace` - Get full trace for execution
  - Response: Complete trace with all spans in hierarchical structure
- MUST provide `GET /traces/{trace_id}/spans` - Get spans for trace
  - Query params: `node_type`, `status`, `min_duration`, `max_duration`
  - Response: Filtered list of spans

**FR-4.2: Real-Time Streaming**
- SHOULD extend WebSocket endpoint to stream span events as they occur
- SHOULD send span start/end events with minimal latency (< 100ms)
- SHOULD support subscribing to specific execution traces

**FR-4.3: Performance**
- MUST respond to trace queries within 500ms for typical workflows (< 100 nodes)
- MUST support pagination for large result sets
- SHOULD implement caching for frequently accessed traces

### FR-5: Frontend - Trace Tab

**FR-5.1: Tab Integration**
- MUST add "Trace" tab to workflow canvas page
- MUST position Trace tab after "Execution" tab and before "Readiness" tab
- MUST maintain consistent UI patterns with existing tabs

**FR-5.2: Trace List View**
- MUST display list of traces for current workflow
- MUST show trace metadata:
  - Execution ID / Run number
  - Start time
  - Duration
  - Status (completed, failed, cancelled)
  - Total span count
- MUST support sorting by time, duration, status
- MUST support filtering by date range, status

**FR-5.3: Trace Detail View**
- MUST visualize trace as hierarchical timeline (waterfall/Gantt chart)
- MUST show parent-child span relationships
- MUST display timing information:
  - Absolute start/end times
  - Relative timing (offset from trace start)
  - Duration for each span
  - Percentage of total execution time
- MUST color-code spans by status (success = green, error = red, pending = yellow)
- MUST support expanding/collapsing span hierarchy

**FR-5.4: Span Details Panel**
- MUST show detailed information when span is selected:
  - Node name and type
  - Start/end timestamps
  - Duration
  - Status
  - Attributes (key-value pairs)
  - Events (if any)
  - Error information (if failed)
- SHOULD support copying span data to clipboard
- SHOULD highlight critical path (longest execution sequence)

**FR-5.5: Interactive Features**
- MUST support zooming and panning timeline
- MUST support searching/filtering spans by name, type, or attributes
- SHOULD support comparing traces side-by-side
- SHOULD support exporting trace visualization as image/JSON

**FR-5.6: Real-Time Updates**
- SHOULD update trace view in real-time as workflow executes
- SHOULD show "live" indicator for ongoing executions
- SHOULD handle concurrent span updates gracefully

### FR-6: Developer Experience

**FR-6.1: Custom Instrumentation**
- SHOULD provide decorator for instrumenting custom nodes:
  ```python
  @trace_node(name="my_custom_node")
  async def my_node(state: State) -> dict:
      ...
  ```
- SHOULD provide context manager for manual span creation:
  ```python
  with create_span("operation_name", attributes={...}):
      ...
  ```
- SHOULD document instrumentation patterns in developer guide

**FR-6.2: Configuration**
- MUST support disabling tracing globally (via config flag)
- MUST support per-workflow tracing enable/disable
- SHOULD support sampling rate configuration (e.g., trace 10% of executions)
- SHOULD support customizing span attribute capture (e.g., exclude inputs/outputs)

**FR-6.3: Testing**
- MUST provide test utilities for asserting span creation
- MUST provide mock trace provider for unit tests
- SHOULD provide example workflows with instrumentation

---

## Non-Functional Requirements

### NFR-1: Performance

**NFR-1.1: Overhead**
- Tracing instrumentation MUST add < 10% overhead to workflow execution time
- Span creation MUST take < 1ms on average
- Trace storage MUST NOT block workflow execution (async/background processing)

**NFR-1.2: Scalability**
- MUST support workflows with up to 1000 nodes
- MUST support storing 100,000 traces per workflow
- MUST handle 10 concurrent trace queries without degradation

**NFR-1.3: Resource Usage**
- Trace storage MUST NOT exceed 100MB per 1000 executions (compressed)
- In-memory trace buffer MUST be bounded (configurable, default 10,000 spans)

### NFR-2: Reliability

**NFR-2.1: Fault Tolerance**
- Trace collection MUST NOT cause workflow failures
- Span storage failures MUST be logged but not propagated
- MUST gracefully handle trace storage unavailability (fall back to in-memory buffer)

**NFR-2.2: Data Integrity**
- MUST guarantee trace-execution correlation (no orphaned spans)
- MUST maintain span hierarchy integrity (parent-child relationships)
- SHOULD detect and report data corruption

### NFR-3: Security

**NFR-3.1: Data Sanitization**
- MUST NOT capture sensitive data in span attributes (credentials, API keys, PII)
- SHOULD provide attribute sanitization hooks
- SHOULD support allowlist/blocklist for attribute names

**NFR-3.2: Access Control**
- MUST respect existing workflow access controls for trace viewing
- MUST NOT expose traces from unauthorized workflows
- SHOULD support role-based access to trace data (admin, developer, viewer)

**NFR-3.3: Data Retention**
- MUST support configurable retention policies
- MUST support secure deletion of expired traces
- SHOULD support compliance with data protection regulations (GDPR, etc.)

### NFR-4: Compatibility

**NFR-4.1: Standards Compliance**
- MUST follow OpenTelemetry specification v1.0+
- MUST use standard semantic conventions where applicable
- SHOULD be compatible with OpenTelemetry Collector

**NFR-4.2: Backward Compatibility**
- MUST NOT break existing workflow execution APIs
- MUST maintain compatibility with existing RunHistoryStore
- SHOULD support gradual rollout (feature flag)

**NFR-4.3: Browser Support**
- Trace UI MUST work in Chrome, Firefox, Safari, Edge (latest 2 versions)
- MUST be responsive (support desktop and tablet, mobile optional)

### NFR-5: Maintainability

**NFR-5.1: Code Quality**
- MUST pass all linting checks (`make lint`, `make canvas-lint`)
- MUST maintain 100% test coverage for core instrumentation logic
- MUST follow existing code style and patterns

**NFR-5.2: Documentation**
- MUST document all public APIs (docstrings, type hints)
- MUST provide architecture diagrams for trace flow
- MUST include examples in developer documentation

**NFR-5.3: Observability of Observability**
- SHOULD log tracing system errors and warnings
- SHOULD expose metrics about tracing system health (span creation rate, storage errors, etc.)
- SHOULD support health checks for trace storage

---

## Out of Scope (Future Work)

The following features are explicitly out of scope for the initial implementation:

1. **Advanced Visualizations:**
   - Service dependency graphs
   - Trace comparison/diff view
   - Anomaly detection and alerting

2. **Metrics Integration:**
   - OpenTelemetry Metrics (counters, histograms)
   - Prometheus integration
   - Custom dashboards (Grafana, etc.)

3. **Logs Integration:**
   - OpenTelemetry Logs
   - Structured logging correlation
   - Log aggregation from spans

4. **Advanced Export:**
   - Direct integration with cloud providers (AWS X-Ray, Google Cloud Trace)
   - Custom export formats (Parquet, Avro)
   - Batch export API

5. **AI-Powered Analysis:**
   - Automatic root cause analysis
   - Performance regression detection
   - Trace-based workflow recommendations

6. **Multi-Workflow Tracing:**
   - Distributed tracing across sub-workflows
   - Cross-workflow correlation
   - Service mesh integration

These features may be considered for future milestones based on user feedback and adoption.

---

## Acceptance Criteria

The feature is considered complete when:

1. ✅ OpenTelemetry SDK integrated into backend with configurable providers
2. ✅ All node types automatically instrumented with span creation
3. ✅ Trace data persisted in SQLite/PostgreSQL with OpenTelemetry schema
4. ✅ API endpoints implemented for trace retrieval and filtering
5. ✅ Trace tab added to Canvas workflow page
6. ✅ Trace visualization shows hierarchical timeline with timing data
7. ✅ Span details panel shows complete span information
8. ✅ Real-time trace updates via WebSocket
9. ✅ All tests pass (`make test`, `make canvas-test`)
10. ✅ All linting passes (`make lint`, `make canvas-lint`)
11. ✅ Documentation complete (design.md, developer guide, API docs)
12. ✅ Performance overhead < 10% measured on benchmark workflows
13. ✅ Manual QA completed with 3+ complex workflows
14. ✅ Security review completed (no sensitive data leakage)

---

## Dependencies

### Technical Dependencies
- **OpenTelemetry SDK** (`opentelemetry-api`, `opentelemetry-sdk`)
- **OpenTelemetry Instrumentation** (`opentelemetry-instrumentation`)
- **OpenTelemetry Exporter** (`opentelemetry-exporter-otlp` or in-memory)
- **SQLite/PostgreSQL** (existing, schema extension needed)
- **React Flow** (existing, for timeline visualization)
- **WebSocket** (existing, extension needed)

### Workflow Dependencies
- Existing execution history system (`RunHistoryStore`)
- Existing WebSocket streaming infrastructure
- Existing workflow execution pipeline (`workflow_execution.py`)
- Existing Canvas tab architecture

### Organizational Dependencies
- Design approval for trace visualization UI
- Security review for data sanitization approach
- Performance benchmarking environment/tooling

---

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Performance overhead exceeds 10% | High | Medium | Implement sampling, async processing, benchmarking early |
| Span context lost in async execution | High | Medium | Thorough testing of async context propagation, use proven patterns |
| Storage growth exceeds expectations | Medium | High | Implement aggressive retention policies, compression, monitoring |
| Trace visualization too complex | Medium | Medium | User testing, iterative design, start with simple MVP |
| OpenTelemetry SDK breaking changes | Low | Low | Pin versions, monitor release notes, automated dependency updates |
| Security: PII leakage in spans | High | Low | Mandatory sanitization, security review, automated scanning |

---

## Timeline Estimate

| Phase | Duration | Tasks |
|-------|----------|-------|
| Phase 1: Backend Foundation | 2-3 days | OpenTelemetry setup, basic instrumentation, span storage |
| Phase 2: Backend Completion | 3-4 days | Full instrumentation, API endpoints, testing |
| Phase 3: Frontend Foundation | 2-3 days | Trace tab UI, API client, basic list view |
| Phase 4: Frontend Visualization | 3-5 days | Timeline view, hierarchical display, span details |
| Phase 5: Polish & Documentation | 2-3 days | E2E testing, documentation, bug fixes |
| **Total** | **12-18 days** | **~2-3 weeks for single full-time developer** |

---

## References

- [OpenTelemetry Specification](https://opentelemetry.io/docs/specs/otel/)
- [OpenTelemetry Python SDK](https://opentelemetry-python.readthedocs.io/)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Orcheo Roadmap - Milestone 6](../roadmap.md)
