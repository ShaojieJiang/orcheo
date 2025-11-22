# Project Plan

## For Conversational Search Node Package

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-11-25
- **Status:** Draft

---

## Overview

This plan translates the Conversational Search PRD and Design into a sequenced delivery roadmap spanning ingestion, retrieval, conversation management, guardrails, and evaluation. It focuses on shipping graph-ready Orcheo nodes with validated configs, reference graphs, and quality gates that satisfy the performance, security, and testing requirements outlined in the requirements and design documents.

**Related Documents:**
- Requirements: [PRD: Conversational Search Node Package](requirements.md)
- Design: [Design Document](design.md)

---

## Milestones

### Milestone 1: MVP Ingestion & Retrieval Loop

**Description:** Deliver the baseline RAG pipeline enabling ingestion, hybrid retrieval, and grounded generation suitable for research pods. Success criteria: p95 retrieval latency ≤ 1.5s, grounded responses with citations, and passing integration tests for the reference graph.

#### Task Checklist

- [ ] Task 1.1: Implement ingestion primitives (DocumentLoaderNode, ChunkingStrategyNode, MetadataExtractorNode, EmbeddingIndexerNode) with schema validation and Pinecone adapter.
  - Dependencies: Access to embedding model provider and Pinecone credentials.
- [ ] Task 1.2: Ship retrieval stack (VectorSearchNode, BM25SearchNode) plus HybridFusionNode with RRF/weighted strategies.
  - Dependencies: Task 1.1 indexed corpus; BaseVectorStore abstraction.
- [ ] Task 1.3: Add core query processing (QueryRewriteNode, CoreferenceResolverNode, QueryClassifierNode, ContextCompressorNode) to improve retrieval quality.
  - Dependencies: Conversation state schema; Task 1.2 retrievers.
- [ ] Task 1.4: Deliver GroundedGeneratorNode with citation emission and backoff/retry semantics.
  - Dependencies: Retrieved context from Task 1.2; LLM provider access.
- [ ] Task 1.5: Provide reference graph and integration tests under `tests/nodes/conversational_search/` covering ingestion → retrieval → generation.
  - Dependencies: Tasks 1.1-1.4.

---

### Milestone 2: Conversational Features & Memory

**Description:** Enhance multi-turn quality and session continuity for early adopters. Success criteria: conversation accuracy improves ≥ 15%, session persistence validated, and topic shifts handled gracefully.

#### Task Checklist

- [ ] Task 2.1: Introduce conversation management nodes (ConversationStateNode, ConversationCompressorNode) with token-budgeted summaries.
  - Dependencies: Milestone 1 graph skeleton.
- [ ] Task 2.2: Add TopicShiftDetectorNode and QueryClarificationNode for adaptive routing and ambiguity resolution.
  - Dependencies: Task 2.1 conversation signals.
- [ ] Task 2.3: Implement MemorySummarizerNode writing to BaseMemoryStore with retention policies.
  - Dependencies: Memory store backend decision; Task 2.1 state schema.
- [ ] Task 2.4: Extend integration tests for multi-turn flows, including conversation compression and topic shift branching.
  - Dependencies: Tasks 2.1-2.3.

---

### Milestone 3: Production Hardening & Guardrails

**Description:** Achieve production readiness with guardrails, performance targets, and caching. Success criteria: generation p95 latency ≤ 4s, hallucination rate < 5%, cache hit rate ≥ 30%, and structured error handling.

#### Task Checklist

- [ ] Task 3.1: Add reliability/performance nodes (IncrementalIndexerNode, StreamingGeneratorNode) with retries and backpressure.
  - Dependencies: Milestone 1 ingestion pipeline; streaming transport choice.
- [ ] Task 3.2: Implement guardrail and routing nodes (HallucinationGuardNode, ReRankerNode, SourceRouterNode, CitationsFormatterNode).
  - Dependencies: Task 3.1 streaming/generation plumbing; policy definitions.
- [ ] Task 3.3: Introduce optimization nodes (AnswerCachingNode, SessionManagementNode, MultiHopPlannerNode) with configurable limits.
  - Dependencies: Task 3.2 guardrails; BaseMemoryStore readiness.
- [ ] Task 3.4: Add performance and failure-mode tests (latency benchmarks, vector store/LLM retry coverage, structured errors).
  - Dependencies: Tasks 3.1-3.3.

---

### Milestone 4: Research, Evaluation, and Compliance

**Description:** Provide evaluation harnesses, analytics, and compliance controls to enable continuous improvement and safe operations. Success criteria: evaluation pipelines operational, compliance audits passing, and feedback loop established.

#### Task Checklist

- [ ] Task 4.1: Build evaluation nodes (DatasetNode, RetrievalEvaluationNode, AnswerQualityEvaluationNode, LLMJudgeNode) with metric reporting.
  - Dependencies: Milestone 1-3 graph artifacts; labeled datasets.
- [ ] Task 4.2: Ship analytics and experimentation nodes (FailureAnalysisNode, ABTestingNode, UserFeedbackCollectionNode, FeedbackIngestionNode, AnalyticsExportNode).
  - Dependencies: Task 4.1 evaluation outputs; data sinks configured.
- [ ] Task 4.3: Implement compliance/privacy controls (PolicyComplianceNode, MemoryPrivacyNode) with audit logging.
  - Dependencies: Legal/compliance guidance; memory store hooks.
- [ ] Task 4.4: Add synthetic data and augmentation support (DataAugmentationNode, TurnAnnotationNode) to expand training corpora.
  - Dependencies: Task 4.1 datasets; LLM provider access.
- [ ] Task 4.5: Extend regression and A/B tests to gate rollouts using evaluation metrics and feedback signals.
  - Dependencies: Tasks 4.1-4.4.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-11-25 | Codex | Initial draft |
