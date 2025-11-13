# OpenTelemetry Tracing Implementation Plan

## Overview

This document provides a detailed, phase-by-phase implementation plan for adding OpenTelemetry-based distributed tracing to Orcheo with a dedicated Trace tab in the Canvas UI.

**Last Updated:** 2025-11-13
**Status:** Draft
**Estimated Duration:** 2-3 weeks (single full-time developer)
**Related Documents:**
- [Requirements Document](./requirements.md)
- [Design Document](./design.md)
- [Milestone 6 Roadmap](../roadmap.md)

---

## Table of Contents

1. [Implementation Phases](#implementation-phases)
2. [Phase-by-Phase Task Breakdown](#phase-by-phase-task-breakdown)
3. [Testing Strategy](#testing-strategy)
4. [Deployment & Rollout](#deployment--rollout)
5. [Success Metrics](#success-metrics)

---

## Implementation Phases

### Phase Overview

| Phase | Focus | Duration | Deliverables |
|-------|-------|----------|--------------|
| **Phase 1** | Backend Foundation | 2-3 days | OpenTelemetry SDK setup, basic instrumentation, span storage schema |
| **Phase 2** | Backend Completion | 3-4 days | Full node instrumentation, API endpoints, comprehensive testing |
| **Phase 3** | Frontend Foundation | 2-3 days | Trace tab UI, API client, trace list view |
| **Phase 4** | Frontend Visualization | 3-5 days | Span timeline, hierarchical view, detail panels, real-time updates |
| **Phase 5** | Polish & Documentation | 2-3 days | E2E testing, documentation, performance tuning, bug fixes |

### Dependencies Between Phases

```
Phase 1 (Backend Foundation)
    │
    ├─> Phase 2 (Backend Completion)
    │       │
    │       └─> Phase 3 (Frontend Foundation)
    │               │
    │               └─> Phase 4 (Frontend Visualization)
    │                       │
    └───────────────────────┴─> Phase 5 (Polish & Documentation)
```

**Note:** Phase 3 can begin once Phase 1 is complete (parallel development possible).

---

## Phase-by-Phase Task Breakdown

## Phase 1: Backend Foundation (2-3 days, ~16-24 hours)

### Goals
- Set up OpenTelemetry SDK infrastructure
- Create basic workflow instrumentation
- Implement span storage schema and SQLite backend
- Create initial trace API endpoint

### Tasks

#### Task 1.1: OpenTelemetry SDK Setup (4-6 hours)

**Files to create:**
- `apps/backend/src/orcheo_backend/app/tracing/__init__.py`
- `apps/backend/src/orcheo_backend/app/tracing/config.py`
- `apps/backend/src/orcheo_backend/app/tracing/provider.py`

**Steps:**
1. Add dependencies to `apps/backend/pyproject.toml`:
   ```toml
   dependencies = [
       # ... existing dependencies
       "opentelemetry-api>=1.20.0",
       "opentelemetry-sdk>=1.20.0",
       "opentelemetry-instrumentation>=0.41b0",
   ]
   ```

2. Run `uv lock` to update lockfile

3. Create `TracingConfig` dataclass:
   - Configuration fields (enabled, exporter_type, sampling_rate, etc.)
   - Environment variable loader (`load_config_from_env()`)
   - Sensitive key defaults for sanitization

4. Create `OrcheoTracerProvider` class:
   - Initialize TracerProvider with resource attributes
   - Configure BatchSpanProcessor
   - Support multiple exporter types (in-memory, console, OTLP)
   - Implement graceful shutdown

5. Create global setup/teardown functions:
   - `setup_tracing(config: TracingConfig)`
   - `get_tracer(name: str) -> Tracer`
   - `shutdown_tracing()`

6. Integrate into FastAPI app lifecycle:
   ```python
   # In main.py
   from .tracing.provider import setup_tracing, shutdown_tracing
   from .tracing.config import load_config_from_env

   @app.on_event("startup")
   async def startup():
       config = load_config_from_env()
       setup_tracing(config)

   @app.on_event("shutdown")
   async def shutdown():
       shutdown_tracing()
   ```

**Testing:**
- Create `tests/backend/test_tracing_config.py`
  - Test config loading from env vars
  - Test config defaults
  - Test sensitive key sanitization

- Create `tests/backend/test_tracing_provider.py`
  - Test TracerProvider initialization
  - Test tracer retrieval
  - Test shutdown behavior

**Acceptance Criteria:**
- ✅ OpenTelemetry SDK imports without errors
- ✅ TracerProvider initializes successfully
- ✅ Tracer can be retrieved via `get_tracer()`
- ✅ All tests pass

---

#### Task 1.2: Span Storage Schema (4-6 hours)

**Files to create:**
- `apps/backend/src/orcheo_backend/app/tracing/models.py`
- `apps/backend/src/orcheo_backend/app/tracing/span_store.py`
- `apps/backend/src/orcheo_backend/app/tracing/sqlite_store.py`

**Steps:**

1. Create data models in `models.py`:
   ```python
   @dataclass
   class SpanRecord:
       span_id: str
       trace_id: str
       parent_span_id: Optional[str]
       name: str
       kind: str
       start_time: datetime
       end_time: Optional[datetime]
       duration_ms: int
       status: str
       attributes: dict[str, Any]
       events: list[dict[str, Any]]

   @dataclass
   class TraceRecord:
       trace_id: str
       workflow_id: str
       execution_id: Optional[str]
       status: str
       started_at: datetime
       ended_at: Optional[datetime]
       duration_ms: Optional[int]
       span_count: int
       spans: list[SpanRecord]

   def span_to_record(span: ReadableSpan) -> SpanRecord:
       """Convert OpenTelemetry ReadableSpan to SpanRecord."""
       ...
   ```

2. Define `TraceStore` protocol in `span_store.py`:
   - `append_span(span: SpanRecord) -> None`
   - `fetch_trace(trace_id: str) -> Optional[TraceRecord]`
   - `fetch_traces_by_workflow(workflow_id, limit, offset, ...) -> list[TraceRecord]`
   - `fetch_trace_by_execution(execution_id) -> Optional[TraceRecord]`
   - `delete_trace(trace_id) -> None`
   - `cleanup_old_traces(retention_days) -> int`

3. Implement `SqliteTraceStore` in `sqlite_store.py`:
   - Create schema (tables: `traces`, `spans`)
   - Implement all TraceStore methods
   - Add proper indexing for performance
   - Handle async SQLite operations with `aiosqlite`

4. Create custom exporter:
   ```python
   # In exporters.py
   class OrcheoSpanExporter(SpanExporter):
       def __init__(self, trace_store: TraceStore):
           self.trace_store = trace_store

       def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
           for span in spans:
               record = span_to_record(span)
               asyncio.create_task(self.trace_store.append_span(record))
           return SpanExportResult.SUCCESS
   ```

**Testing:**
- Create `tests/backend/test_tracing_models.py`
  - Test SpanRecord creation
  - Test TraceRecord creation
  - Test `span_to_record()` conversion

- Create `tests/backend/test_tracing_sqlite_store.py`
  - Test schema creation
  - Test span appending
  - Test trace fetching
  - Test cleanup

**Acceptance Criteria:**
- ✅ Database schema created successfully
- ✅ Spans can be stored and retrieved
- ✅ Trace metadata updated correctly
- ✅ All storage tests pass

---

#### Task 1.3: Basic Workflow Instrumentation (4-6 hours)

**Files to modify:**
- `apps/backend/src/orcheo_backend/app/workflow_execution.py`

**Files to create:**
- `apps/backend/src/orcheo_backend/app/tracing/instrumentation.py`

**Steps:**

1. Create instrumentation decorators in `instrumentation.py`:
   - `@trace_workflow()` - for workflow execution
   - `@trace_node()` - for node execution
   - Context managers for manual span creation

2. Add basic workflow instrumentation:
   ```python
   # In workflow_execution.py
   from .tracing.instrumentation import trace_workflow
   from .tracing.provider import get_tracer

   @trace_workflow(name="workflow.execute")
   async def execute_workflow_with_websocket(
       compiled_graph,
       state,
       execution_id: str,
       workflow_id: str,
       websocket,
       history_store,
       trace_store,  # NEW: inject trace_store
   ):
       tracer = get_tracer(__name__)

       # Decorator creates root span automatically
       # Add workflow-level attributes
       current_span = trace.get_current_span()
       current_span.set_attribute("workflow.id", workflow_id)
       current_span.set_attribute("execution.id", execution_id)

       # Continue with existing execution logic
       async for step in compiled_graph.astream(state, config=config):
           await history_store.append_step(execution_id, step)
           await websocket.send_json(step)

       # Span automatically ends when function returns
   ```

3. Update dependency injection to provide `trace_store`:
   ```python
   # In dependencies.py
   from .tracing.span_store import TraceStore
   from .tracing.sqlite_store import SqliteTraceStore

   _trace_store: Optional[TraceStore] = None

   def get_trace_store() -> TraceStore:
       global _trace_store
       if _trace_store is None:
           db_path = os.getenv("ORCHEO_TRACE_DB_PATH", "./traces.db")
           _trace_store = SqliteTraceStore(db_path)
       return _trace_store
   ```

**Testing:**
- Create `tests/backend/test_tracing_instrumentation.py`
  - Test `@trace_workflow` decorator creates spans
  - Test span attributes set correctly
  - Test error handling (exceptions recorded in spans)
  - Test async context propagation

**Acceptance Criteria:**
- ✅ Workflow execution creates root span
- ✅ Span attributes include workflow_id and execution_id
- ✅ Spans exported to trace store
- ✅ Instrumentation tests pass

---

#### Task 1.4: Initial API Endpoint (2-4 hours)

**Files to create:**
- `apps/backend/src/orcheo_backend/app/routers/traces.py`
- `apps/backend/src/orcheo_backend/app/schemas/traces.py`

**Steps:**

1. Create response schemas in `schemas/traces.py`:
   ```python
   class SpanResponse(BaseModel):
       span_id: str
       trace_id: str
       parent_span_id: Optional[str]
       name: str
       kind: str
       start_time: datetime
       end_time: Optional[datetime]
       duration_ms: int
       status: str
       attributes: dict[str, Any]
       events: list[dict[str, Any]]

   class TraceDetailResponse(BaseModel):
       trace_id: str
       workflow_id: str
       execution_id: Optional[str]
       status: str
       started_at: datetime
       ended_at: Optional[datetime]
       duration_ms: Optional[int]
       span_count: int
       spans: list[SpanResponse]

       @classmethod
       def from_record(cls, record: TraceRecord) -> "TraceDetailResponse":
           ...

   class TraceListResponse(BaseModel):
       traces: list[TraceDetailResponse]
       total: int
       limit: int
       offset: int
   ```

2. Create router in `routers/traces.py`:
   - Implement `GET /api/workflows/{workflow_id}/traces`
   - Basic pagination support

3. Register router in main app:
   ```python
   # In main.py
   from .routers import traces
   app.include_router(traces.router)
   ```

**Testing:**
- Create `tests/backend/test_tracing_api.py`
  - Test trace list endpoint
  - Test pagination
  - Test filtering by workflow_id
  - Test empty results

**Acceptance Criteria:**
- ✅ Endpoint returns trace data successfully
- ✅ Pagination works correctly
- ✅ API tests pass

---

### Phase 1 Milestone

**Definition of Done:**
- All Phase 1 tests pass (`pytest tests/backend/test_tracing_*.py`)
- Linting passes (`make lint`)
- Basic workflow execution creates and stores spans
- API endpoint returns stored trace data
- Code reviewed and merged to feature branch

---

## Phase 2: Backend Completion (3-4 days, ~24-32 hours)

### Goals
- Instrument all node types automatically
- Implement complete API surface
- Add data sanitization
- Comprehensive backend testing
- WebSocket span streaming

### Tasks

#### Task 2.1: Node-Level Instrumentation (6-8 hours)

**Files to modify:**
- `src/orcheo/nodes/base.py`
- `src/orcheo/nodes/ai_node.py`
- `src/orcheo/nodes/task_node.py`
- `src/orcheo/nodes/decision_node.py`

**Steps:**

1. Add instrumentation to `BaseNode.__call__()`:
   ```python
   # In base.py
   from orcheo_backend.app.tracing.instrumentation import trace_node

   class BaseNode:
       @trace_node(capture_input=True, capture_output=True)
       async def __call__(self, state: State) -> dict:
           """Execute node with automatic tracing."""
           decoded_state = self.decode_variables(state)
           result = await self.run(decoded_state)
           return result
   ```

2. Add node-specific attributes in subclasses:
   ```python
   # In ai_node.py
   class AINode(BaseNode):
       async def run(self, state: State) -> dict:
           span = trace.get_current_span()
           span.set_attribute("ai.model", self.model)
           span.set_attribute("ai.temperature", self.temperature)

           result = await self._invoke_model(state)

           # Track token usage
           if "usage" in result:
               span.set_attribute("ai.tokens.input", result["usage"]["input_tokens"])
               span.set_attribute("ai.tokens.output", result["usage"]["output_tokens"])

           return result
   ```

3. Handle error cases consistently:
   - Ensure exceptions are recorded in spans
   - Set span status to ERROR
   - Capture error type, message, stacktrace

**Testing:**
- Create `tests/test_node_instrumentation.py`
  - Test each node type creates spans
  - Test node-specific attributes captured
  - Test error handling
  - Test token metrics for AINode

**Acceptance Criteria:**
- ✅ All node types instrumented
- ✅ Spans created for every node execution
- ✅ Node-specific attributes captured
- ✅ Node instrumentation tests pass

---

#### Task 2.2: Data Sanitization (4-6 hours)

**Files to create:**
- `apps/backend/src/orcheo_backend/app/tracing/sanitization.py`

**Steps:**

1. Implement sanitization functions:
   ```python
   def sanitize_value(
       value: Any,
       config: TracingConfig,
       max_depth: int = 5,
   ) -> Any:
       """
       Recursively sanitize values to remove sensitive data.

       - Redacts keys matching sensitive_keys
       - Truncates long strings
       - Limits collection sizes
       - Respects max recursion depth
       """
       ...

   def is_sensitive_key(key: str, sensitive_keys: list[str]) -> bool:
       """Check if key name contains sensitive terms."""
       key_lower = key.lower()
       return any(sk in key_lower for sk in sensitive_keys)
   ```

2. Integrate into instrumentation decorators:
   ```python
   # In instrumentation.py
   @trace_node(...)
   def wrapper(...):
       if capture_input:
           sanitized = sanitize_value(input_data, config)
           span.set_attribute("node.input", sanitized)
   ```

3. Add configuration for sanitization behavior:
   - Allow customizing sensitive_keys
   - Allow enabling/disabling input/output capture
   - Support truncation limits

**Testing:**
- Create `tests/backend/test_tracing_sanitization.py`
  - Test sensitive key detection
  - Test value redaction
  - Test string truncation
  - Test nested dictionary handling
  - Test list/array handling

**Acceptance Criteria:**
- ✅ Sensitive data not captured in spans
- ✅ Large values truncated appropriately
- ✅ Sanitization tests pass
- ✅ Security review completed

---

#### Task 2.3: Complete API Endpoints (4-6 hours)

**Files to modify:**
- `apps/backend/src/orcheo_backend/app/routers/traces.py`

**Steps:**

1. Implement remaining endpoints:
   - `GET /api/executions/{execution_id}/trace`
   - `GET /api/traces/{trace_id}`
   - `DELETE /api/traces/{trace_id}` (admin only)

2. Add filtering and query parameters:
   - Date range filtering (`start_date`, `end_date`)
   - Status filtering (`status=completed|failed|running`)
   - Span filtering by node type, duration

3. Add error handling:
   - 404 for missing traces
   - 403 for unauthorized access
   - 400 for invalid parameters

4. Integrate with authentication:
   ```python
   @router.get("/workflows/{workflow_id}/traces")
   async def list_traces(
       workflow_id: str,
       current_user: User = Depends(get_current_user),
       trace_store: TraceStore = Depends(get_trace_store),
   ):
       # Check access
       if not await has_workflow_access(current_user, workflow_id):
           raise HTTPException(status_code=403)
       ...
   ```

**Testing:**
- Update `tests/backend/test_tracing_api.py`
  - Test all endpoints
  - Test filtering and pagination
  - Test authentication/authorization
  - Test error cases

**Acceptance Criteria:**
- ✅ All API endpoints implemented
- ✅ Filtering works correctly
- ✅ Authentication enforced
- ✅ API tests comprehensive and passing

---

#### Task 2.4: WebSocket Span Streaming (4-6 hours)

**Files to modify:**
- `apps/backend/src/orcheo_backend/app/routers/websocket.py`
- `apps/backend/src/orcheo_backend/app/workflow_execution.py`

**Steps:**

1. Extend WebSocket message types:
   ```python
   # New message type
   {
       "type": "span",
       "data": {
           "span_id": "...",
           "trace_id": "...",
           "name": "...",
           "status": "started|completed|failed",
           "duration_ms": 123,
           ...
       }
   }
   ```

2. Stream spans in real-time during execution:
   ```python
   # In workflow_execution.py
   async def execute_workflow_with_websocket(...):
       # Hook into span processor to get spans as they complete
       async for step in compiled_graph.astream(...):
           # Existing step streaming
           await websocket.send_json({"type": "step", "data": step})

           # NEW: Stream span events
           if span_completed:
               await websocket.send_json({
                   "type": "span",
                   "data": span_to_dict(span)
               })
   ```

3. Create span event listener:
   ```python
   class WebSocketSpanProcessor(SpanProcessor):
       """Span processor that pushes spans to WebSocket."""

       def __init__(self, websocket):
           self.websocket = websocket

       def on_end(self, span: ReadableSpan):
           asyncio.create_task(
               self.websocket.send_json({
                   "type": "span",
                   "data": span_to_dict(span)
               })
           )
   ```

**Testing:**
- Create `tests/backend/test_tracing_websocket.py`
  - Test span messages sent via WebSocket
  - Test message format
  - Test real-time delivery
  - Test multiple concurrent clients

**Acceptance Criteria:**
- ✅ Spans streamed in real-time
- ✅ WebSocket clients receive span events
- ✅ No performance degradation
- ✅ WebSocket tests pass

---

#### Task 2.5: Backend Testing & Documentation (4-6 hours)

**Steps:**

1. Comprehensive integration tests:
   - Create `tests/backend/test_tracing_integration.py`
   - Test end-to-end flow: workflow execution → span creation → storage → API retrieval
   - Test multiple concurrent workflows
   - Test error scenarios

2. Performance testing:
   - Benchmark span creation overhead
   - Measure API response times
   - Test with large workflows (100+ nodes)

3. Backend documentation:
   - Document all modules with docstrings
   - Add inline comments for complex logic
   - Update API documentation (OpenAPI schema)

**Acceptance Criteria:**
- ✅ Integration tests pass
- ✅ Performance overhead < 10%
- ✅ All code documented
- ✅ `make lint` and `make test` pass

---

### Phase 2 Milestone

**Definition of Done:**
- All backend functionality complete
- All tests pass (unit + integration)
- Performance benchmarks met
- Code documented
- Security review completed
- API fully functional and tested

---

## Phase 3: Frontend Foundation (2-3 days, ~16-24 hours)

### Goals
- Add Trace tab to Canvas UI
- Create API client for trace endpoints
- Implement basic trace list view
- Set up real-time WebSocket integration

### Tasks

#### Task 3.1: Trace Tab Integration (4-6 hours)

**Files to modify:**
- `apps/canvas/src/features/workflow/components/panels/workflow-tabs.tsx`
- `apps/canvas/src/features/workflow/pages/workflow-canvas/components/workflow-canvas-layout.tsx`

**Files to create:**
- `apps/canvas/src/features/workflow/pages/workflow-canvas/components/trace-tab-content.tsx`

**Steps:**

1. Add "Trace" tab to `workflow-tabs.tsx`:
   ```typescript
   <TabsTrigger value="trace" className="gap-1.5 text-sm px-3 py-1.5">
     Trace
   </TabsTrigger>
   ```

2. Add Trace tab content to `workflow-canvas-layout.tsx`:
   ```typescript
   <TabsContent
     value="trace"
     className="flex-1 m-0 p-0 overflow-hidden min-h-0"
   >
     <TraceTabContent {...traceProps} />
   </TabsContent>
   ```

3. Create basic `TraceTabContent` component:
   ```typescript
   export function TraceTabContent({
     workflowId,
     activeExecutionId,
   }: TraceTabContentProps) {
     return (
       <div className="flex h-full w-full">
         <div className="flex-1 flex items-center justify-center">
           <p className="text-muted-foreground">
             Select a trace to view details
           </p>
         </div>
       </div>
     );
   }
   ```

4. Wire up tab switching logic in parent page component

**Testing:**
- Manual testing: verify tab appears and is clickable
- Create `trace-tab-content.test.tsx`
  - Test component renders
  - Test props handling

**Acceptance Criteria:**
- ✅ Trace tab visible after Execution tab
- ✅ Tab switches correctly
- ✅ Component renders without errors

---

#### Task 3.2: API Client & Types (4-6 hours)

**Files to create:**
- `apps/canvas/src/features/workflow/api/traces.ts`
- `apps/canvas/src/features/workflow/types/trace.ts`

**Steps:**

1. Define TypeScript types in `types/trace.ts`:
   ```typescript
   export interface SpanRecord {
     span_id: string;
     trace_id: string;
     parent_span_id: string | null;
     name: string;
     kind: string;
     start_time: Date;
     end_time: Date | null;
     duration_ms: number;
     status: "OK" | "ERROR" | "UNSET";
     attributes: Record<string, any>;
     events: Array<{
       timestamp: Date;
       name: string;
       attributes: Record<string, any>;
     }>;
   }

   export interface TraceRecord {
     trace_id: string;
     workflow_id: string;
     execution_id: string | null;
     status: "running" | "completed" | "failed";
     started_at: Date;
     ended_at: Date | null;
     duration_ms: number | null;
     span_count: number;
     spans: SpanRecord[];
   }

   export interface TraceListResponse {
     traces: TraceRecord[];
     total: number;
     limit: number;
     offset: number;
   }
   ```

2. Create API client in `api/traces.ts`:
   ```typescript
   export const tracesApi = {
     async listWorkflowTraces(
       workflowId: string,
       params?: {
         limit?: number;
         offset?: number;
         start_date?: Date;
         end_date?: Date;
       }
     ): Promise<TraceListResponse> {
       const queryParams = new URLSearchParams();
       if (params?.limit) queryParams.set("limit", String(params.limit));
       if (params?.offset) queryParams.set("offset", String(params.offset));
       // ... add other params

       const response = await fetch(
         `/api/workflows/${workflowId}/traces?${queryParams}`,
         { credentials: "include" }
       );

       if (!response.ok) throw new Error("Failed to fetch traces");

       const data = await response.json();
       return {
         ...data,
         traces: data.traces.map(deserializeTrace),
       };
     },

     async getExecutionTrace(executionId: string): Promise<TraceRecord> {
       const response = await fetch(`/api/executions/${executionId}/trace`, {
         credentials: "include",
       });

       if (!response.ok) throw new Error("Failed to fetch trace");

       return deserializeTrace(await response.json());
     },
   };

   function deserializeTrace(raw: any): TraceRecord {
     return {
       ...raw,
       started_at: new Date(raw.started_at),
       ended_at: raw.ended_at ? new Date(raw.ended_at) : null,
       spans: raw.spans.map(deserializeSpan),
     };
   }

   function deserializeSpan(raw: any): SpanRecord {
     return {
       ...raw,
       start_time: new Date(raw.start_time),
       end_time: raw.end_time ? new Date(raw.end_time) : null,
       events: raw.events.map((e: any) => ({
         ...e,
         timestamp: new Date(e.timestamp),
       })),
     };
   }
   ```

**Testing:**
- Create `tests/api/traces.test.ts`
  - Mock API responses
  - Test successful requests
  - Test error handling
  - Test date deserialization

**Acceptance Criteria:**
- ✅ API client functions implemented
- ✅ TypeScript types defined
- ✅ Date parsing works correctly
- ✅ API client tests pass

---

#### Task 3.3: React Hooks for Trace Data (4-6 hours)

**Files to create:**
- `apps/canvas/src/features/workflow/hooks/use-traces.ts`
- `apps/canvas/src/features/workflow/hooks/use-trace-websocket.ts`

**Steps:**

1. Create `use-traces` hook:
   ```typescript
   export function useTraces(workflowId: string) {
     const [traces, setTraces] = useState<TraceRecord[]>([]);
     const [isLoading, setIsLoading] = useState(true);
     const [error, setError] = useState<string | null>(null);

     const fetchTraces = useCallback(async () => {
       setIsLoading(true);
       setError(null);

       try {
         const response = await tracesApi.listWorkflowTraces(workflowId);
         setTraces(response.traces);
       } catch (err) {
         setError(err instanceof Error ? err.message : "Failed to fetch traces");
       } finally {
         setIsLoading(false);
       }
     }, [workflowId]);

     useEffect(() => {
       fetchTraces();
     }, [fetchTraces]);

     return {
       traces,
       isLoading,
       error,
       refetch: fetchTraces,
     };
   }
   ```

2. Create `use-trace-websocket` hook for real-time updates:
   ```typescript
   export function useTraceWebSocket(
     workflowId: string,
     onSpanEvent: (span: SpanRecord) => void
   ) {
     const wsRef = useRef<WebSocket | null>(null);

     useEffect(() => {
       // Connect to WebSocket
       const ws = new WebSocket(`ws://localhost:8000/ws/workflow/${workflowId}`);

       ws.onmessage = (event) => {
         const message = JSON.parse(event.data);

         if (message.type === "span") {
           const span = deserializeSpan(message.data);
           onSpanEvent(span);
         }
       };

       wsRef.current = ws;

       return () => {
         ws.close();
       };
     }, [workflowId, onSpanEvent]);

     return wsRef;
   }
   ```

**Testing:**
- Create `tests/hooks/use-traces.test.ts`
  - Test loading states
  - Test error handling
  - Test refetch functionality

**Acceptance Criteria:**
- ✅ Hooks implemented
- ✅ Data fetching works
- ✅ WebSocket integration functional
- ✅ Hook tests pass

---

#### Task 3.4: Trace List Panel (4-6 hours)

**Files to create:**
- `apps/canvas/src/features/workflow/components/panels/trace-list-panel.tsx`

**Steps:**

1. Create trace list component:
   ```typescript
   export function TraceListPanel({
     traces,
     selectedTraceId,
     onSelectTrace,
     onRefresh,
     isLoading,
     error,
   }: TraceListPanelProps) {
     return (
       <div className="flex flex-col h-full">
         {/* Header with refresh button */}
         <div className="border-b border-border p-2 flex items-center justify-between">
           <h3 className="font-semibold">Traces</h3>
           <Button size="sm" variant="outline" onClick={onRefresh}>
             <RefreshCw className="h-4 w-4" />
           </Button>
         </div>

         {/* Trace list */}
         <div className="flex-1 overflow-auto">
           {isLoading && <LoadingSpinner />}
           {error && <ErrorMessage message={error} />}
           {traces.map(trace => (
             <TraceListItem
               key={trace.trace_id}
               trace={trace}
               isSelected={selectedTraceId === trace.trace_id}
               onClick={() => onSelectTrace(trace.trace_id)}
             />
           ))}
         </div>
       </div>
     );
   }

   function TraceListItem({ trace, isSelected, onClick }: TraceListItemProps) {
     return (
       <div
         className={cn(
           "p-2 border-b cursor-pointer hover:bg-muted/50",
           isSelected && "bg-muted"
         )}
         onClick={onClick}
       >
         <div className="flex items-center justify-between">
           <div className="text-sm font-medium">
             Execution #{trace.execution_id}
           </div>
           <Badge className={getStatusBadgeClass(trace.status)}>
             {trace.status}
           </Badge>
         </div>
         <div className="text-xs text-muted-foreground mt-1">
           {formatDate(trace.started_at)}
         </div>
         <div className="text-xs text-muted-foreground">
           {trace.span_count} spans • {formatDuration(trace.duration_ms)}
         </div>
       </div>
     );
   }
   ```

2. Integrate into `TraceTabContent`:
   ```typescript
   export function TraceTabContent({ workflowId }: TraceTabContentProps) {
     const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
     const { traces, isLoading, error, refetch } = useTraces(workflowId);

     return (
       <SidebarLayout
         sidebar={
           <TraceListPanel
             traces={traces}
             selectedTraceId={selectedTraceId}
             onSelectTrace={setSelectedTraceId}
             onRefresh={refetch}
             isLoading={isLoading}
             error={error}
           />
         }
         sidebarWidth={320}
         resizable
       >
         <div className="flex items-center justify-center h-full">
           {selectedTraceId ? (
             <p>Trace details will appear here</p>
           ) : (
             <p className="text-muted-foreground">Select a trace</p>
           )}
         </div>
       </SidebarLayout>
     );
   }
   ```

**Testing:**
- Create `tests/components/trace-list-panel.test.tsx`
  - Test rendering with traces
  - Test empty state
  - Test loading state
  - Test error state
  - Test selection

**Acceptance Criteria:**
- ✅ Trace list displays correctly
- ✅ Selection works
- ✅ Refresh works
- ✅ Component tests pass

---

### Phase 3 Milestone

**Definition of Done:**
- Trace tab functional and integrated
- API client working and tested
- Trace list view implemented
- Basic UI functional
- `make canvas-test` passes
- `make canvas-lint` passes

---

## Phase 4: Frontend Visualization (3-5 days, ~24-40 hours)

### Goals
- Implement span timeline visualization (waterfall/Gantt chart)
- Create hierarchical span tree view
- Build span details panel
- Add interactive features (zoom, filter, search)
- Implement real-time trace updates

### Tasks

#### Task 4.1: Span Timeline Component (8-12 hours)

**Files to create:**
- `apps/canvas/src/features/workflow/components/panels/span-timeline.tsx`

**Steps:**

1. Design timeline layout:
   - Left column: span names (hierarchical tree)
   - Right column: timeline bars (Gantt chart)
   - Header: time axis with markers

2. Implement timeline calculations:
   ```typescript
   function calculateTimelineBounds(spans: SpanRecord[]) {
     const startTimes = spans.map(s => s.start_time.getTime());
     const endTimes = spans
       .filter(s => s.end_time)
       .map(s => s.end_time!.getTime());

     const minTime = Math.min(...startTimes);
     const maxTime = Math.max(...endTimes);

     return {
       minTime,
       maxTime,
       totalDuration: maxTime - minTime,
     };
   }

   function getSpanPosition(
     span: SpanRecord,
     minTime: number,
     totalDuration: number
   ): { left: string; width: string } {
     const start = span.start_time.getTime();
     const end = span.end_time?.getTime() || Date.now();

     const leftPercent = ((start - minTime) / totalDuration) * 100;
     const widthPercent = ((end - start) / totalDuration) * 100;

     return {
       left: `${leftPercent}%`,
       width: `${Math.max(widthPercent, 0.5)}%`,
     };
   }
   ```

3. Build hierarchical span tree:
   ```typescript
   interface SpanNode {
     span: SpanRecord;
     children: SpanNode[];
     depth: number;
   }

   function buildSpanHierarchy(spans: SpanRecord[]): SpanNode[] {
     const rootSpans = spans.filter(s => !s.parent_span_id);

     function buildTree(parent: SpanRecord, depth: number = 0): SpanNode {
       const children = spans
         .filter(s => s.parent_span_id === parent.span_id)
         .map(child => buildTree(child, depth + 1));

       return { span: parent, children, depth };
     }

     return rootSpans.map(root => buildTree(root));
   }
   ```

4. Render timeline rows:
   ```typescript
   function SpanRow({
     node,
     minTime,
     totalDuration,
     onSpanClick,
     selectedSpanId,
   }: SpanRowProps) {
     const position = getSpanPosition(node.span, minTime, totalDuration);
     const color = getSpanColor(node.span.status);
     const isSelected = selectedSpanId === node.span.span_id;

     return (
       <>
         <div className="flex items-center h-8 border-b hover:bg-muted/50">
           {/* Span name */}
           <div
             className="flex-none w-64 px-2 truncate text-xs"
             style={{ paddingLeft: `${node.depth * 20 + 8}px` }}
           >
             {node.span.name}
           </div>

           {/* Timeline container */}
           <div className="flex-1 relative">
             <div
               className={cn(
                 "absolute top-1 h-6 rounded cursor-pointer",
                 color,
                 isSelected && "ring-2 ring-blue-500"
               )}
               style={{
                 left: position.left,
                 width: position.width,
               }}
               onClick={() => onSpanClick(node.span)}
             />
           </div>
         </div>

         {/* Render children */}
         {node.children.map(child => (
           <SpanRow
             key={child.span.span_id}
             node={child}
             minTime={minTime}
             totalDuration={totalDuration}
             onSpanClick={onSpanClick}
             selectedSpanId={selectedSpanId}
           />
         ))}
       </>
     );
   }
   ```

5. Add timeline header with time markers:
   ```typescript
   function TimelineHeader({ minTime, maxTime, totalDuration }: TimelineHeaderProps) {
     const markers = generateTimeMarkers(minTime, maxTime);

     return (
       <div className="flex h-8 border-b bg-muted/30">
         <div className="flex-none w-64" />
         <div className="flex-1 relative">
           {markers.map(marker => (
             <div
               key={marker.time}
               className="absolute top-0 bottom-0 border-l border-border/50"
               style={{ left: `${((marker.time - minTime) / totalDuration) * 100}%` }}
             >
               <span className="text-xs text-muted-foreground ml-1">
                 {formatTime(marker.time)}
               </span>
             </div>
           ))}
         </div>
       </div>
     );
   }
   ```

**Testing:**
- Create `tests/components/span-timeline.test.tsx`
  - Test timeline rendering
  - Test span positioning
  - Test hierarchy rendering
  - Test selection

**Acceptance Criteria:**
- ✅ Timeline displays spans correctly
- ✅ Hierarchy visible with indentation
- ✅ Timing calculations accurate
- ✅ Interactive (click to select)
- ✅ Component tests pass

---

#### Task 4.2: Span Details Panel (4-6 hours)

**Files to create:**
- `apps/canvas/src/features/workflow/components/panels/span-details-panel.tsx`

**Steps:**

1. Create details panel component:
   ```typescript
   export function SpanDetailsPanel({
     span,
     onClose,
   }: SpanDetailsPanelProps) {
     if (!span) return null;

     return (
       <div className="border-l border-border h-full w-80 flex flex-col">
         {/* Header */}
         <div className="flex items-center justify-between p-4 border-b">
           <h3 className="font-semibold">Span Details</h3>
           <Button size="sm" variant="ghost" onClick={onClose}>
             <X className="h-4 w-4" />
           </Button>
         </div>

         {/* Content */}
         <div className="flex-1 overflow-auto p-4 space-y-4">
           {/* Basic info */}
           <div>
             <h4 className="text-sm font-medium mb-2">Information</h4>
             <dl className="space-y-1 text-sm">
               <dt className="text-muted-foreground">Name</dt>
               <dd className="font-mono">{span.name}</dd>

               <dt className="text-muted-foreground">Status</dt>
               <dd>
                 <Badge className={getStatusBadgeClass(span.status)}>
                   {span.status}
                 </Badge>
               </dd>

               <dt className="text-muted-foreground">Duration</dt>
               <dd>{formatDuration(span.duration_ms)}</dd>

               <dt className="text-muted-foreground">Start Time</dt>
               <dd>{formatTimestamp(span.start_time)}</dd>

               <dt className="text-muted-foreground">End Time</dt>
               <dd>{span.end_time ? formatTimestamp(span.end_time) : "In progress"}</dd>
             </dl>
           </div>

           {/* Attributes */}
           <div>
             <h4 className="text-sm font-medium mb-2">Attributes</h4>
             <AttributesList attributes={span.attributes} />
           </div>

           {/* Events */}
           {span.events.length > 0 && (
             <div>
               <h4 className="text-sm font-medium mb-2">Events</h4>
               <EventsList events={span.events} />
             </div>
           )}
         </div>
       </div>
     );
   }

   function AttributesList({ attributes }: { attributes: Record<string, any> }) {
     return (
       <dl className="space-y-1 text-sm">
         {Object.entries(attributes).map(([key, value]) => (
           <div key={key} className="grid grid-cols-2 gap-2">
             <dt className="text-muted-foreground truncate">{key}</dt>
             <dd className="font-mono text-xs break-all">
               {JSON.stringify(value)}
             </dd>
           </div>
         ))}
       </dl>
     );
   }
   ```

2. Integrate into `TraceViewer`:
   ```typescript
   export function TraceViewer({ trace }: TraceViewerProps) {
     const [selectedSpan, setSelectedSpan] = useState<SpanRecord | null>(null);

     return (
       <div className="flex h-full">
         <div className="flex-1">
           <SpanTimeline
             spans={trace?.spans || []}
             onSpanClick={setSelectedSpan}
             selectedSpanId={selectedSpan?.span_id}
           />
         </div>
         {selectedSpan && (
           <SpanDetailsPanel
             span={selectedSpan}
             onClose={() => setSelectedSpan(null)}
           />
         )}
       </div>
     );
   }
   ```

**Testing:**
- Create `tests/components/span-details-panel.test.tsx`
  - Test rendering with span data
  - Test attributes display
  - Test events display
  - Test close functionality

**Acceptance Criteria:**
- ✅ Details panel displays span information
- ✅ Attributes formatted correctly
- ✅ Events shown (if present)
- ✅ Component tests pass

---

#### Task 4.3: Interactive Features (6-8 hours)

**Steps:**

1. Add search/filter functionality:
   ```typescript
   function TraceFilters({
     onFilterChange,
   }: TraceFiltersProps) {
     const [search, setSearch] = useState("");
     const [statusFilter, setStatusFilter] = useState<string[]>([]);
     const [nodeTypeFilter, setNodeTypeFilter] = useState<string[]>([]);

     return (
       <div className="p-2 border-b space-y-2">
         <Input
           placeholder="Search spans..."
           value={search}
           onChange={(e) => {
             setSearch(e.target.value);
             onFilterChange({ search: e.target.value, statusFilter, nodeTypeFilter });
           }}
         />

         <div className="flex gap-2">
           <Select
             value={statusFilter}
             onValueChange={(values) => {
               setStatusFilter(values);
               onFilterChange({ search, statusFilter: values, nodeTypeFilter });
             }}
             multiple
           >
             <SelectTrigger>
               <SelectValue placeholder="Filter by status" />
             </SelectTrigger>
             <SelectContent>
               <SelectItem value="OK">Success</SelectItem>
               <SelectItem value="ERROR">Error</SelectItem>
               <SelectItem value="UNSET">In Progress</SelectItem>
             </SelectContent>
           </Select>
         </div>
       </div>
     );
   }
   ```

2. Implement span filtering logic:
   ```typescript
   function filterSpans(
     spans: SpanRecord[],
     filters: {
       search?: string;
       statusFilter?: string[];
       nodeTypeFilter?: string[];
     }
   ): SpanRecord[] {
     return spans.filter(span => {
       if (filters.search && !span.name.toLowerCase().includes(filters.search.toLowerCase())) {
         return false;
       }

       if (filters.statusFilter?.length && !filters.statusFilter.includes(span.status)) {
         return false;
       }

       if (filters.nodeTypeFilter?.length) {
         const nodeType = span.attributes["node.type"];
         if (!nodeType || !filters.nodeTypeFilter.includes(nodeType)) {
           return false;
         }
       }

       return true;
     });
   }
   ```

3. Add zoom/pan functionality (optional, using a library like `react-zoom-pan-pinch`):
   ```typescript
   import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";

   function ZoomableTimeline({ children }: { children: React.ReactNode }) {
     return (
       <TransformWrapper
         minScale={0.5}
         maxScale={5}
         initialScale={1}
       >
         <TransformComponent>
           {children}
         </TransformComponent>
       </TransformWrapper>
     );
   }
   ```

4. Add keyboard shortcuts:
   ```typescript
   useEffect(() => {
     function handleKeyDown(e: KeyboardEvent) {
       if (e.key === "Escape") {
         setSelectedSpan(null);
       }
       if (e.key === "f" && e.metaKey) {
         e.preventDefault();
         focusSearch();
       }
     }

     window.addEventListener("keydown", handleKeyDown);
     return () => window.removeEventListener("keydown", handleKeyDown);
   }, []);
   ```

**Testing:**
- Test filtering works correctly
- Test search functionality
- Test keyboard shortcuts

**Acceptance Criteria:**
- ✅ Filtering functional
- ✅ Search works
- ✅ Keyboard shortcuts work
- ✅ UX smooth and responsive

---

#### Task 4.4: Real-Time Updates (4-6 hours)

**Steps:**

1. Integrate WebSocket span updates into timeline:
   ```typescript
   export function TraceViewer({ trace, workflowId }: TraceViewerProps) {
     const [spans, setSpans] = useState<SpanRecord[]>(trace?.spans || []);

     useTraceWebSocket(workflowId, (newSpan) => {
       setSpans(prev => {
         // Check if span already exists (update) or is new (append)
         const existingIndex = prev.findIndex(s => s.span_id === newSpan.span_id);

         if (existingIndex >= 0) {
           // Update existing span
           const updated = [...prev];
           updated[existingIndex] = newSpan;
           return updated;
         } else {
           // Append new span
           return [...prev, newSpan];
         }
       });
     });

     return (
       <SpanTimeline
         spans={spans}
         // ... other props
       />
     );
   }
   ```

2. Add "live" indicator for ongoing executions:
   ```typescript
   {trace?.status === "running" && (
     <Badge variant="outline" className="animate-pulse">
       <Circle className="h-2 w-2 fill-green-500 mr-1" />
       Live
     </Badge>
   )}
   ```

3. Auto-scroll to new spans (optional):
   ```typescript
   const timelineRef = useRef<HTMLDivElement>(null);

   useEffect(() => {
     if (autoScroll && timelineRef.current) {
       timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
     }
   }, [spans]);
   ```

**Testing:**
- Manual testing with live workflow execution
- Verify spans appear in real-time
- Test performance with rapid span updates

**Acceptance Criteria:**
- ✅ Real-time updates functional
- ✅ UI updates smoothly
- ✅ No performance degradation
- ✅ Live indicator displays correctly

---

### Phase 4 Milestone

**Definition of Done:**
- Timeline visualization complete and polished
- Span details panel functional
- Interactive features working (filter, search)
- Real-time updates integrated
- All frontend tests pass
- UI/UX reviewed and approved
- `make canvas-lint` and `make canvas-test` pass

---

## Phase 5: Polish & Documentation (2-3 days, ~16-24 hours)

### Goals
- End-to-end integration testing
- Performance optimization
- Comprehensive documentation
- Bug fixes and polish

### Tasks

#### Task 5.1: End-to-End Testing (6-8 hours)

**Steps:**

1. Create E2E test suite:
   ```typescript
   // tests/e2e/trace-tab.spec.ts
   describe("Trace Tab", () => {
     it("should display traces for a workflow", async () => {
       // Navigate to workflow page
       // Switch to Trace tab
       // Verify trace list appears
       // Select a trace
       // Verify timeline displays
       // Click on a span
       // Verify details panel opens
     });

     it("should show real-time updates during execution", async () => {
       // Start workflow execution
       // Switch to Trace tab
       // Verify spans appear in real-time
       // Verify trace completes
     });

     it("should filter spans correctly", async () => {
       // Open trace with multiple spans
       // Apply status filter
       // Verify filtered results
       // Apply search
       // Verify search results
     });
   });
   ```

2. Test complex scenarios:
   - Large workflows (100+ nodes)
   - Concurrent executions
   - Error scenarios
   - Network failures (retry logic)

3. Performance testing:
   - Measure render times for large traces
   - Benchmark WebSocket message handling
   - Test memory usage during long executions

**Acceptance Criteria:**
- ✅ E2E tests pass
- ✅ Complex scenarios handled correctly
- ✅ Performance benchmarks met

---

#### Task 5.2: Documentation (6-8 hours)

**Steps:**

1. Update architecture docs:
   - Add tracing architecture diagram to `docs/design.md`
   - Document trace data flow
   - Explain OpenTelemetry integration

2. Create developer guide:
   ```markdown
   # docs/developer_guide.md

   ## Instrumenting Custom Nodes

   ### Using the @trace_node Decorator

   To automatically instrument a custom node:

   ```python
   from orcheo_backend.app.tracing.instrumentation import trace_node

   class MyCustomNode(BaseNode):
       @trace_node(capture_input=True, capture_output=True)
       async def run(self, state: State) -> dict:
           # Your node logic here
           result = await some_operation(state)
           return result
   ```

   ### Adding Custom Span Attributes

   ```python
   from opentelemetry import trace

   class MyCustomNode(BaseNode):
       async def run(self, state: State) -> dict:
           span = trace.get_current_span()
           span.set_attribute("custom.attribute", "value")
           # ... continue execution
   ```
   ```

3. Create user guide:
   ```markdown
   # docs/trace_tab_user_guide.md

   ## Using the Trace Tab

   ### Viewing Execution Traces

   1. Navigate to a workflow in Canvas
   2. Click the "Trace" tab
   3. Select a trace from the list
   4. Explore the timeline visualization

   ### Understanding the Timeline

   - Each horizontal bar represents a node execution (span)
   - Colors indicate status: green (success), red (error), yellow (in progress)
   - Indentation shows parent-child relationships
   - Bar width indicates duration

   ### Inspecting Span Details

   - Click any span in the timeline
   - View detailed information in the right panel
   - See node inputs, outputs, and metadata
   ```

4. Update API documentation:
   - Document all trace endpoints in OpenAPI schema
   - Add examples and response samples

5. Add inline code comments:
   - Document complex algorithms
   - Explain design decisions
   - Add TODOs for future improvements

**Acceptance Criteria:**
- ✅ Architecture docs updated
- ✅ Developer guide complete
- ✅ User guide written
- ✅ API docs updated
- ✅ Code well-commented

---

#### Task 5.3: Bug Fixes & Polish (4-8 hours)

**Steps:**

1. Fix identified bugs from testing
2. Polish UI/UX:
   - Improve loading states
   - Better error messages
   - Smooth animations
   - Responsive design tweaks

3. Performance optimizations:
   - Optimize span rendering (virtualization for large lists)
   - Reduce unnecessary re-renders
   - Optimize database queries

4. Accessibility improvements:
   - Keyboard navigation
   - Screen reader support
   - ARIA labels

**Acceptance Criteria:**
- ✅ All known bugs fixed
- ✅ UI polished and professional
- ✅ Performance optimized
- ✅ Accessibility standards met

---

### Phase 5 Milestone

**Definition of Done:**
- All tests pass (unit + integration + E2E)
- All linting passes (`make lint`, `make canvas-lint`)
- Documentation complete and reviewed
- Performance benchmarks met
- No known critical bugs
- Feature ready for production

---

## Testing Strategy

### Unit Tests

**Backend:**
- `tests/backend/test_tracing_*.py` - All tracing modules
- Coverage target: 100% for core instrumentation logic
- Mock external dependencies (OpenTelemetry SDK, database)

**Frontend:**
- `tests/components/*.test.tsx` - All React components
- `tests/hooks/*.test.ts` - All custom hooks
- `tests/api/*.test.ts` - API client
- Coverage target: 90%+

### Integration Tests

**Backend:**
- `tests/backend/test_tracing_integration.py`
  - End-to-end flow: workflow → spans → storage → API
  - WebSocket streaming
  - Multi-workflow scenarios

**Frontend:**
- Test API client with mock server
- Test WebSocket integration

### End-to-End Tests

- Full user journeys:
  - Create workflow → Execute → View trace
  - Real-time trace updates
  - Filtering and search
- Use Playwright or similar tool

### Performance Tests

- Benchmark span creation overhead
- Measure API response times
- Test timeline rendering with 100+ spans
- Stress test WebSocket with rapid updates

---

## Deployment & Rollout

### Deployment Strategy

1. **Feature Flag**
   - Add `ORCHEO_TRACING_ENABLED` env var (default: `true` in dev, `false` in prod initially)
   - Allow gradual rollout

2. **Database Migration**
   - Run migration to create `traces` and `spans` tables
   - No downtime required (additive schema change)

3. **Staged Rollout**
   - Deploy to development environment
   - Internal testing (1-2 days)
   - Deploy to staging
   - Beta user testing (3-5 days)
   - Deploy to production with feature flag off
   - Gradually enable for users (10% → 50% → 100%)

### Rollback Plan

- Disable tracing via feature flag
- No data loss (existing workflows continue working)
- Trace data remains in database for future re-enable

---

## Success Metrics

### Development Metrics
- ✅ All tests pass (100% of test suite green)
- ✅ Code coverage ≥ 90% for frontend, 100% for backend core
- ✅ Zero linting errors
- ✅ Performance overhead < 10%

### User Metrics (Post-Launch)
- Trace tab usage rate (% of users who view traces)
- Average time spent in Trace tab
- User feedback score
- Bug reports related to tracing

### Technical Metrics
- Trace storage growth rate
- API response times (p50, p95, p99)
- WebSocket connection stability
- Span creation latency

---

## Risk Mitigation

### High-Priority Risks

1. **Performance Degradation**
   - **Mitigation:** Early benchmarking, sampling, async processing
   - **Fallback:** Feature flag to disable tracing

2. **Data Privacy**
   - **Mitigation:** Mandatory sanitization, security review
   - **Fallback:** Allowlist-only attribute capture

3. **Storage Growth**
   - **Mitigation:** Retention policies, cleanup jobs, compression
   - **Fallback:** Reduce retention period, increase cleanup frequency

4. **Complex Implementation**
   - **Mitigation:** Phased approach, regular code reviews
   - **Fallback:** Reduce scope to MVP if timeline at risk

---

## Next Steps

1. Review and approve this plan
2. Set up project tracking (GitHub issues/project board)
3. Begin Phase 1 implementation
4. Schedule regular check-ins (daily standups, weekly reviews)

---

**Document Status:** Ready for Review
**Approval Required From:** Tech Lead, Product Owner
**Target Start Date:** TBD
**Target Completion Date:** TBD
