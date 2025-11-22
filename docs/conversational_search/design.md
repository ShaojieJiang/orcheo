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

## Security Considerations

- Rely on Orcheo secret bindings for vector stores, LLMs, and web connectors; redact secrets in logs and stored configs.
- Enforce PolicyComplianceNode and MemoryPrivacyNode for PII/toxicity filtering and retention controls.
- Validate inputs for connectors and query classifiers; guard against prompt injection in WebSearchNode responses.
- Support rate limiting and abuse detection at the node orchestration layer for public-facing flows.

## Performance Considerations

- Ingestion throughput target ≥ 500 documents/minute across DocumentLoaderNode → Chunking → EmbeddingIndexerNode.
- Retrieval p95 latency ≤ 1.5s for hybrid dense/sparse flows; cache frequent queries via AnswerCachingNode.
- Generation p95 latency ≤ 4s with streaming transports when available; ContextCompressorNode enforces token budgets.
- Implement retry/backoff semantics through NodeResult status handling for transient failures.

## Testing Strategy

- **Unit tests:** Cover node configurations, schema validators, retriever fusion logic, guardrail decisions, and memory operations.
- **Integration tests:** End-to-end conversational search graph under `tests/nodes/conversational_search/` validating ingestion → retrieval → generation with citations.
- **Manual QA checklist:** Session lifecycle (creation/cleanup), ambiguous query clarification, hybrid retrieval correctness, streaming generator stability, and compliance/guardrail enforcement.

## Rollout Plan

1. Phase 1: Internal/flag-gated MVP delivering ingestion, query processing, retrieval, and grounded generation.
2. Phase 2: Enable conversation management, clarification, and metadata enrichment for early adopters with monitoring.
3. Phase 3: Production hardening with routing, caching, compliance, and streaming UX upgrades.
4. Phase 4: Ongoing evaluation, analytics, and experimentation via ABTestingNode and metrics exports.

Feature flags control node availability and fusion strategies; maintain backward compatibility by keeping stable node configs and schema validators during upgrades.

## Open Issues

- [ ] Finalize adapter roadmap beyond Pinecone (e.g., PGVector, LanceDB) and prioritize based on adopter surveys.
- [ ] Determine default models for ReRankerNode and CoreferenceResolverNode with reproducible baselines.
- [ ] Define telemetry schema for AnalyticsExportNode and feedback ingestion sinks.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-11-18 | Shaojie Jiang | Initial draft |
