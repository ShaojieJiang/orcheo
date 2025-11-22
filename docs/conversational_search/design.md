# Design Document

## For Conversational Search Node Package

- **Version:** 0.1
- **Author:** Shaojie Jiang
- **Date:** 2025-11-18
- **Status:** Draft

---

## Overview

The Conversational Search Node Package provides a cohesive set of Orcheo nodes that cover ingestion, retrieval, fusion, grounding, and answer generation for multi-turn search workflows. The goal is to standardize how builders compose conversational retrieval pipelines without bespoke glue code, offering interchangeable components for dense and sparse search, conversation-aware query processing, and grounded response generation.

The package lives under `orcheo.nodes.conversational_search` and supplies shared abstractions for vector stores, memory stores, and retrievers. It emphasizes configuration-first APIs, validated schemas, and guardrails such as hallucination and compliance checks so operations teams can deploy conversational agents confidently while swapping vendors or algorithms as needed.

## Components

- **Ingestion & Indexing (Data Platform / Backend)**
  - Handles DocumentLoaderNode, ChunkingStrategyNode, MetadataExtractorNode, EmbeddingIndexerNode, and IncrementalIndexerNode.
  - Interfaces with external connectors (file, web, API), embedding providers, and vector databases (Pinecone v1 first).

- **Retrieval Layer (Search / ML)**
  - Hosts VectorSearchNode, BM25SearchNode, HybridFusionNode, WebSearchNode, ReRankerNode, and SourceRouterNode.
  - Depends on base retriever interfaces, vector store abstractions, and optional web/graph search adapters.

- **Query Processing & Conversation (ML / Backend)**
  - Implements QueryRewriteNode, CoreferenceResolverNode, QueryClassifierNode, ContextCompressorNode, ConversationStateNode, ConversationCompressorNode, TopicShiftDetectorNode, and MemorySummarizerNode.
  - Relies on memory stores, tokenizer utilities, and LLM-based classifiers/resolvers.

- **Generation & Guardrails (ML / Safety)**
  - Includes GroundedGeneratorNode, StreamingGeneratorNode, HallucinationGuardNode, CitationsFormatterNode, and QueryClarificationNode.
  - Integrates with LLM providers that support streaming and with evidence payloads emitted by retrieval.

- **Optimization, Compliance, & Evaluation (Ops / Research)**
  - Covers AnswerCachingNode, SessionManagementNode, MultiHopPlannerNode, PolicyComplianceNode, MemoryPrivacyNode, DatasetNode, RetrievalEvaluationNode, AnswerQualityEvaluationNode, TurnAnnotationNode, LLMJudgeNode, DataAugmentationNode, FailureAnalysisNode, UserFeedbackCollectionNode, FeedbackIngestionNode, ABTestingNode, and AnalyticsExportNode.
  - Hooks into analytics sinks, evaluation datasets, and feature flagging/traffic allocation services.

## Request Flows

### Flow 1: Basic Conversational Search

1. ConversationStateNode initializes or retrieves session state.
2. QueryRewriteNode and CoreferenceResolverNode reshape the user query using history.
3. VectorSearchNode and BM25SearchNode execute dense and sparse retrieval; HybridFusionNode merges results (e.g., RRF).
4. ContextCompressorNode deduplicates and trims context to token budgets.
5. GroundedGeneratorNode produces an answer with citations; HallucinationGuardNode validates output.
6. CitationsFormatterNode structures references and returns the response to the user.

### Flow 2: Hybrid Retrieval with Re-ranking

1. DocumentLoaderNode and ChunkingStrategyNode ingest and prepare content; EmbeddingIndexerNode writes to the vector store.
2. SourceRouterNode selects VectorSearchNode, BM25SearchNode, or WebSearchNode based on query classification.
3. HybridFusionNode combines retriever outputs; ReRankerNode scores top-k results.
4. ContextCompressorNode enforces token limits; GroundedGeneratorNode streams or returns the final answer.

### Flow 3: Guarded Production Loop

1. SessionManagementNode and ConversationStateNode manage concurrency and lifecycle per session.
2. QueryClassifierNode routes ambiguous intents to QueryClarificationNode; PolicyComplianceNode applies content filters.
3. StreamingGeneratorNode returns partial tokens while HallucinationGuardNode performs LLM-judge checks.
4. AnswerCachingNode stores successful Q&A pairs; AnalyticsExportNode emits metrics.
5. ABTestingNode routes traffic between configurations for experimentation.

## API Contracts

Node contracts follow Orcheo's node interface with typed `NodeConfig` objects and structured `NodeResult` payloads. Example patterns:

```
CONFIG ConversationalSearchConfig
Fields:
  retrievers: List[RetrieverConfig]
  generator: GeneratorConfig
  memory_store: MemoryStoreConfig

RESULT ConversationalSearchResult
Fields:
  message: str
  citations: List[Citation]
  diagnostics: Dict[str, Any]
  status: NodeStatus
```

Representative node schemas (aligned with `orcheo.graph.config.NodeConfig` validation):

- **VectorSearchNode**

  ```yaml
  type: VectorSearchNode
  version: 1
  config:
    vector_store:   # BaseVectorStore implementation
      provider: pinecone
      index_name: conversational-search
      namespace: default
      top_k: 20
      similarity_metric: cosine
    filters:
      allowed_sources: ["kb", "faq"]
      audience: "public"
    return_embeddings: false
  outputs:
    results: list[ScoredDocument]
    diagnostics: Dict[str, Any]
  ```

- **GroundedGeneratorNode**

  ```yaml
  type: GroundedGeneratorNode
  version: 1
  config:
    model: gpt-4o-mini
    system_prompt: "Ground answers in the provided citations."
    temperature: 0.2
    max_tokens: 512
    citations_required: true
    interpolation: "{{conversation.memory.summary}}"  # evaluated against state
  inputs:
    query: str
    context: list[ScoredDocument]
    conversation: ConversationState
  outputs:
    message: str
    citations: list[Citation]
    safety_events: list[GuardrailEvent]
  ```

Key service interactions:
- Vector store APIs (Pinecone v1 adapter initially, extensible to PGVector/LanceDB).
- LLM provider APIs with streaming support for GroundedGeneratorNode/StreamingGeneratorNode.
- External web/graph search adapters for WebSearchNode and SourceRouterNode.

## Data Models / Schemas

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | string | Unique identifier for ingested documents |
| `chunks` | list[Chunk] | Chunked content with offsets and metadata |
| `embedding` | vector<float> | Dense vector written to the vector store |
| `metadata` | map<string, string> | Normalized attributes (title, source, tags) |
| `query_intent` | enum | Classified intent (search, clarify, finalize) |
| `retrieval_result` | list[ScoredDocument] | Ranked documents with scores and sources |
| `conversation_state` | map | Session state, participants, and memory handles |
| `citations` | list[Citation] | URL/title/snippet references returned to clients |
| `metrics` | map | Evaluation metrics (Recall@k, NDCG, MRR, etc.) |

Example citation payload:

```json
{
  "id": "doc-123",
  "url": "https://example.com",
  "title": "Doc title",
  "snippet": "Highlighted text ...",
  "score": 0.82
}
```

### Node state and storage abstractions

- **BaseMemoryStore**: common CRUD contract (`get(session_id) -> ConversationState`, `append(session_id, message)`, `truncate(session_id, ttl)`, `summarize(session_id) -> Summary`). Backed by pluggable drivers (Redis + TTL in phase 1, Postgres JSONB in phase 2, cloud KV in phase 3) with size limits enforced per session (e.g., 50 turns or 200 KB) and periodic compaction via `MemorySummarizerNode`.
- **BaseVectorStore**: interface (`upsert(vectors: list[VectorRecord])`, `query(query_vector, top_k, filters) -> list[ScoredDocument]`, `delete(ids)`, `migrate(namespace)`) with vendor-specific adapters (Pinecone v1 first). Batched writes (100 vectors) and retry with idempotent tokens to isolate transient failures.
- **Inter-node state contract**: nodes receive and emit `state: ConversationState` containing `turns`, `memory_handle`, `active_query`, and `context` references. State mutations are versioned via `state.version` and validated by each node before write-back; incompatible versions raise `NodeResult(status="FAILED", error_code="STATE_VALIDATION")`.
- **Variable interpolation**: `{{path.to.value}}` tokens resolve against the current `state` (conversation scope) and `inputs` (node-local scope) with dotted lookups. Missing values return explicit validation errors to prevent silent fallbacks. Example: `"user:" {{inputs.query}} "history:" {{state.turns[-3:].text}}` inside prompts.

## Security Considerations

- Rely on Orcheo secret bindings for vector stores, LLMs, and web connectors; redact secrets in logs and stored configs.
- Enforce PolicyComplianceNode and MemoryPrivacyNode for PII/toxicity filtering and retention controls.
- Validate inputs for connectors and query classifiers; guard against prompt injection in WebSearchNode responses.
- Support rate limiting and abuse detection at the node orchestration layer for public-facing flows.

## Performance Considerations

- Ingestion throughput target ≥ 500 documents/minute across DocumentLoaderNode → Chunking → EmbeddingIndexerNode.
- Retrieval p95 latency ≤ 1.5s for hybrid dense/sparse flows; cache frequent queries via AnswerCachingNode.
- Generation p95 latency ≤ 4s with streaming transports when available; ContextCompressorNode enforces token budgets.
- Implement retry/backoff semantics through NodeResult status handling for transient failures; guardrail failures (e.g., HallucinationGuardNode, PolicyComplianceNode) return `SOFT_FAIL` with safe fallbacks to clarification rather than dropping the session.
- Memory growth is bounded via per-session quotas and scheduled compaction jobs; eviction policies favor least-recent sessions while persisting summaries to maintain continuity.

## Testing Strategy

- **Unit tests:** Cover node configurations, schema validators, retriever fusion logic, guardrail decisions, and memory operations.
- **Integration tests:** End-to-end conversational search graph under `tests/nodes/conversational_search/` validating ingestion → retrieval → generation with citations, including scenarios for topic shifts, ambiguous queries routed to clarification, and failure handling when guardrails reject outputs.
- **Evaluation tests:** Retrieval/answer quality nodes validated against golden datasets (NDCG@10, Recall@20) and LLM judge comparisons for hallucination guard acceptance rates.
- **Performance regression:** Automated benchmarks measuring ingestion throughput, retrieval p95, and generation p95 on nightly runs with alerts on >10% regression.
- **Manual QA checklist:** Session lifecycle (creation/cleanup), ambiguous query clarification, hybrid retrieval correctness, streaming generator stability, compliance/guardrail enforcement, and state version compatibility across phased rollouts.

## Rollout Plan

1. Phase 1: Internal/flag-gated MVP delivering ingestion, query processing, retrieval, and grounded generation.
2. Phase 2: Enable conversation management, clarification, and metadata enrichment for early adopters with monitoring.
3. Phase 3: Production hardening with routing, caching, compliance, and streaming UX upgrades.
4. Phase 4: Ongoing evaluation, analytics, and experimentation via ABTestingNode and metrics exports.

Feature flags control node availability and fusion strategies; maintain backward compatibility by keeping stable node configs and schema validators during upgrades.

**Dependencies and compatibility guardrails:**
- Phase 1 requires Pinecone adapter and Redis-backed `BaseMemoryStore`; mock adapters are provided for local dev.
- Phase 2 depends on Postgres/pgvector availability for hybrid retrieval experiments and model registry hooks for classifier/generator selection.
- Phase 3 introduces web/graph search adapters, telemetry sinks, and policy engines; rollout uses dual-write to old/new telemetry schemas with compatibility adapters.
- Phased upgrades preserve prior config versions; nodes validate `version` fields and reject incompatible state to avoid silent corruption.

## Open Issues

- [ ] Finalize adapter roadmap beyond Pinecone (e.g., PGVector, LanceDB) with prioritization criteria (existing adopter volume, latency SLOs, and hosting constraints) and a publishable timeline.
- [ ] Determine default models for ReRankerNode and CoreferenceResolverNode with reproducible baselines (public eval sets + latency/cost targets per model family).
- [ ] Define telemetry schema for AnalyticsExportNode and feedback ingestion sinks, referencing Orcheo-wide telemetry conventions (operation name, node_id, correlation_id, timings, guardrail outcomes).

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-11-18 | Shaojie Jiang | Initial draft |
