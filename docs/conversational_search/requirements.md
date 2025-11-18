# Conversational Search Node Package Requirements

## Overview
This document captures the functional and non-functional requirements for a reusable package of Orcheo nodes dedicated to conversational search scenarios. The package targets workflows where users engage in natural-language dialogue to retrieve, refine, and ground knowledge from heterogeneous data sources.

## Objectives
1. Provide a cohesive set of graph-ready nodes for ingestion, retrieval, ranking, grounding, and answer generation.
2. Ensure nodes are composable so builders can swap models, retrievers, or memory stores without rewriting glue logic.
3. Offer observability hooks and guardrails that make it easy to operate conversational search agents in production.

## Scope
- Nodes intended for inclusion under `orcheo.nodes.conversational_search`.
- Shared utilities that the nodes depend upon (e.g., schema validators, telemetry wrappers).
- Documentation and examples necessary for teams to adopt the nodes.

Out of scope: custom UI surfaces, data labeling tooling, or vendor-specific orchestration outside of node contracts.

## Functional Requirements
### 1. Data Ingestion Nodes
- **DocumentLoaderNode**: Accepts file blobs or URLs, normalizes into chunked `Document` objects, and emits metadata (source, mime type, checksum).
- **EmbeddingIndexerNode**: Consumes normalized documents, batches them, computes embeddings (configurable model), and writes to a vector store interface (`BaseVectorStore`). Must support upsert semantics.
- **SyncMonitorNode**: Emits status events for ingestion pipelines (success/failure counts, retry schedules).

### 2. Retrieval & Ranking Nodes
- **RetrieverNode**: Queries one or more `BaseVectorStore` implementations using hybrid (BM25 + dense) retrieval, returning scored `DocumentChunk` items.
- **ReRankerNode**: Applies LLM or cross-encoder re-ranking; configurable top-k, threshold, and fallback modes.
- **ContextCompressorNode**: Deduplicates and compresses context while preserving citations.

### 3. Conversation & Memory Nodes
- **ConversationStateNode**: Maintains dialog state (turn history, entity store, user profile). Pluggable persistence (Redis, Postgres, in-memory) with TTL management.
- **FollowUpClassifierNode**: Determines whether the next action is retrieval, clarification, or final answer.
- **MemorySummarizerNode**: Periodically summarizes long histories into episodic memory slots stored via `BaseMemoryStore`.

### 4. Answer Generation & Grounding Nodes
- **GroundedGeneratorNode**: Invokes LLMs with retrieved context, enforces citation attachment, and emits confidence scores.
- **HallucinationGuardNode**: Validates generated answers against retrieved facts using entailment or rule-based checks; routes to fallback strategies when confidence < threshold.
- **CitationsFormatterNode**: Produces structured references (URL, title, snippet) suitable for UI consumption.

### 5. Tooling & Integration Nodes
- **FeedbackIngestionNode**: Accepts explicit user feedback (thumbs up/down, free-form text) and writes to analytics sinks.
- **TelemetryExportNode**: Exposes OpenTelemetry spans/metrics with node-level attributes (latency, token usage, result quality).
- **PolicyComplianceNode**: Enforces content filters (PII, toxicity) with configurable policies and audit logging.

## Non-Functional Requirements
1. **Configurability**: Each node must expose a `NodeConfig` dataclass with validation and serde; defaults documented.
2. **Observability**: Nodes emit structured events through Orcheo's tracing utilities and support correlation IDs.
3. **Error Handling**: Graceful retries with exponential backoff for transient failures; surfaced via `NodeResult.status`.
4. **Performance**: Baseline targets — ingestion throughput ≥ 500 documents/minute, retrieval p95 latency ≤ 1.5s, generation p95 ≤ 4s (assuming standard GPU-backed LLMs).
5. **Security**: All nodes handling credentials must rely on Orcheo's secret manager bindings and redact sensitive values from logs.
6. **Testing**: Provide unit tests per node plus integration tests for a reference conversational search graph defined under `tests/nodes/conversational_search/`.

## Deliverables
- Node implementations with docstrings and typing.
- Example graph demonstrating ingestion → retrieval → generation pipeline.
- MkDocs reference page summarizing configuration tables and usage notes.
- Automated tests and fixtures.

## Open Questions
1. Which vector store adapters must be supported in v1 (e.g., Pinecone, PGVector, LanceDB)?
2. Preferred hallucination detection approach (LLM judge vs. rule-based)?
3. Data retention requirements for stored conversation history across geographies.
