# PRD: Conversational Search Node Package

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** Conversational Search Node Package
- **Type:** Product
- **Summary:** Reusable package of graph-ready Orcheo nodes covering ingestion, retrieval, ranking, grounding, and answer generation for conversational search workflows where users issue natural-language queries across heterogeneous knowledge.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-11-18

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link |
|-----------|------|
| Prior Artifacts | [Roadmap](../../product/roadmap.md) |
| Design Review | [This document](requirements.md) |
| Design File/Deck | TBD |
| Eng Requirement Doc | TBD |
| Marketing Requirement Doc (if applicable) | N/A |
| Experiment Plan (if applicable) | TBD |
| Rollout Docs (if applicable) | TBD |

## PROBLEM DEFINITION
### Objectives
Deliver a cohesive package of conversational search nodes that lets builders compose ingestion, retrieval, grounding, and generative steps without bespoke glue code. Provide guardrails so production teams can operate and iterate on conversational agents confidently.

### Target users
Graph builders, applied researchers, and operations engineers who assemble conversational search workflows inside Orcheo. They need modular components to ingest data, search heterogeneous sources, craft responses, and monitor deployed agents.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Workflow builder | Drop in nodes for ingestion, chunking, retrieval, fusion, and generation | I can launch conversational search experiments without rewriting infrastructure | P0 | DocumentLoaderNode, ChunkingStrategyNode, ChunkEmbeddingNode, VectorStoreUpsertNode, DenseSearchNode, SparseSearchNode, HybridFusionNode, and GroundedGeneratorNode available with configs |
| Retrieval researcher | Swap retrievers, rankers, and planners while reusing shared interfaces | I can benchmark new strategies quickly | P0 | Base abstractions for retrievers/vector stores/memory plus configurable nodes that are independently testable |
| Operations lead | Enable guardrails and compliance across conversations | I can safely run conversational agents in production | P1 | Guard nodes (HallucinationGuardNode, PolicyComplianceNode), and session/memory controls exposed |

### Context, Problems, Opportunities
Teams currently hand-roll conversational search flows, creating duplicated work and inconsistent abstractions. There is an opportunity to standardize on Orcheo nodes that cover ingestion through evaluation, expose configuration-first APIs, and make it trivial to plug different vendors, memory stores, or retrievers into a conversation-aware loop.

### Product goals and Non-goals
**Goals:** Provide modular nodes for conversational search, ensure composability through shared interfaces, and include guardrails that ease production operations.

**Non-goals:** Custom UI surfaces, data labeling tooling, or vendor-specific orchestration beyond the defined node contracts remain out of scope.

## PRODUCT DEFINITION
### Requirements
Conversational search functionality will live under `orcheo.nodes.conversational_search`, along with shared utilities (schema validators) and the docs/examples needed for adoption. Requirements are split between core conversational search (Priority 0/1) and research, compliance, and operations (Priority 2).

#### Node Overview Summary
| Category | Node | Priority | Purpose |
|----------|------|----------|---------|
| **Data Ingestion** | DocumentLoaderNode | P0 | Connectors for file, web, and API sources with format normalization |
| | ChunkingStrategyNode | P0 | Configurable character/token rules with overlap control for optimal indexing |
| | MetadataExtractorNode | P0 | Attaches structured metadata (title, source, tags) powering filters and ranking |
| | ChunkEmbeddingNode | P0 | Applies embedding functions to chunk text and returns named vector record sets |
| | VectorStoreUpsertNode | P0 | Persists selected embedding sets into BaseVectorStore adapters and reports indexed IDs |
| | IncrementalIndexerNode | P1 | Delta-sync pipeline that detects adds/updates/deletes without full reindexing |
| **Retrieval** | DenseSearchNode | P0 | Dense similarity search built atop the base vector store abstraction |
| | SparseSearchNode | P0 | Keyword retrieval for sparse/deterministic matching |
| | HybridFusionNode | P0 | Merges retriever outputs via Reciprocal Rank Fusion (RRF) or weighted sum strategies |
| | WebSearchNode | P0 | Optional live search for freshness |
| | ReRankerNode | P1 | Cross-encoder or LLM scoring pipeline for top-k results |
| | SourceRouterNode | P1 | Routes to appropriate sources (Tavily for web search, Neo4j for knowledge graphs) via heuristics or learned models |
| **Query Processing** | QueryRewriteNode | P0 | Uses conversation memories to rewrite or expand user questions |
| | CoreferenceResolverNode | P0 | Resolves pronouns/entities using neural approaches (NeuralCoref or transformer-based models) for precise retrieval |
| | QueryClassifierNode | P0 | Routes queries (search vs. clarifying question vs. finalization) using classifiers |
| | ContextCompressorNode | P0 | Deduplicates retrieved context and enforces token budgets |
| **Conversation** | ConversationStateNode | P0 | Maintains per-session context, participants, and runtime state objects |
| | ConversationCompressorNode | P0 | Summarizes long histories with token budgets for downstream nodes |
| | TopicShiftDetectorNode | P0 | AI-based node that flags query divergence with user-configurable sensitivity thresholds |
| | MemorySummarizerNode | P1 | Writes episodic memory back into BaseMemoryStore for personalization |
| **Generation & Guardrails** | GroundedGeneratorNode | P0 | Core generative responder that cites retrieved context |
| | StreamingGeneratorNode | P1 | Streams responses via async iterators for responsive UX |
| | HallucinationGuardNode | P1 | Validates responses using LLM Judge approach with fallback routing |
| | CitationsFormatterNode | P1 | Produces structured reference payloads (URL, title, snippet) |
| | QueryClarificationNode | P1 | Requests additional details from the user when intent is ambiguous |
| **Memory & Optimization** | AnswerCachingNode | P1 | Caches semantically similar Q&A pairs with TTL and similarity policies |
| | SessionManagementNode | P1 | Controls lifecycle, concurrency, and cleanup for session workloads |
| | MultiHopPlannerNode | P1 | Plans sequential retrieval hops when questions require decomposition |
| **Compliance** | PolicyComplianceNode | P1 | Enforces content filters (PII, toxicity) with configurable policies and audit logging |
| | MemoryPrivacyNode | P1 | Applies configurable redaction and retention policies to stored dialog state |
| **Evaluation & Tooling** | DatasetNode | P2 | Manages golden datasets per search scenario with versioning and schema validation |
| | RetrievalEvaluationNode | P2 | Computes Recall@k, MRR, NDCG, MAP using relevance labels |
| | AnswerQualityEvaluationNode | P2 | Scores answers via LLM-as-a-judge or rule-based metrics (faithfulness, relevance, completeness) |
| | TurnAnnotationNode | P2 | Captures structured success/intent labels from human or heuristic sources |
| | LLMJudgeNode | P2 | Runs LLM evaluators on answers vs. references for offline experimentation and regression gating |
| | DataAugmentationNode | P2 | Generates synthetic training data (query variations, negatives, paraphrases) for fine-tuning |
| | FailureAnalysisNode | P2 | Categorizes failure modes (no results, irrelevant results, hallucinations) and emits reports |
| | UserFeedbackCollectionNode | P2 | Collects implicit (clicks, reformulations) and explicit (thumbs, ratings) feedback |
| | FeedbackIngestionNode | P2 | Persists explicit feedback to analytics sinks for aggregation |
| | ABTestingNode | P2 | Routes traffic between configurations, tracks variant assignments, and exports comparison metrics |
| | AnalyticsExportNode | P2 | Sends structured analytics data (query patterns, performance metrics) to warehouses or research tools |

#### Key Dependencies
```
Phase 1 (MVP)
└─ Phase 2 (Conversational)
   └─ Phase 3 (Production Quality)
      └─ Phase 4 (Research & Ops)

Parallel tracks after Phase 1:
- Evaluation nodes (Phase 4) can be built alongside Phase 2-3
- Compliance nodes can be added as needed
```

#### Deliverables
- Node implementations with docstrings and typing.
- Example graph demonstrating ingestion → retrieval → generation pipeline.
- Demo 2.1/2.2 artifacts showing a dedicated indexing run plus the hybrid retrieval/fusion pipeline that assumes those indexes exist.
- MkDocs reference page summarizing configuration tables and usage notes.
- Automated unit tests per node and an integration test for a reference conversational search graph.

### Designs (if applicable)
No dedicated UI designs; relies on node reference docs and example graphs. Figma artifacts TBD as UI or orchestration surfaces emerge.

## TECHNICAL CONSIDERATIONS
The conversational search node package requires a backend engineering pod with ML expertise. Key engineering investments include: (1) base abstractions for vector stores, memory stores, and retrieval interfaces; (2) streaming infrastructure for real-time generation; (3) evaluation harnesses for offline metrics; and (4) integration with Orcheo's existing node registry, state management, and secret binding systems. External dependencies include vector database clients (Pinecone, PGVector, LanceDB), embedding model APIs, and LLM providers with streaming support.

### Architecture Overview
Conversational search nodes plug into Orcheo graphs as modular steps for ingestion, retrieval, planning, and generation. Each node exposes a typed `NodeConfig` and interoperates with shared abstractions (vector stores, memory stores, message buses). The package also ships reference graphs plus schema validators demonstrating how flows connect.

### Technical Requirements
- **Configurability:** Every node exposes validated configs with documented defaults and schema enforcement.
- **Error Handling:** Implement graceful retries with exponential backoff for transient failures via `NodeResult.status` semantics.
- **Performance Targets:** Meet ingestion throughput (≥ 500 docs/minute), retrieval p95 latency (≤ 1.5s), and generation p95 latency (≤ 4s) assuming GPU-backed LLMs.
- **Security:** Nodes handling credentials rely on Orcheo secret bindings and redact sensitive values in logs/storage. Data retention follows Orcheo's global settings.
- **Testing:** Provide unit tests per node plus integration coverage for a reference conversational search graph located under `tests/nodes/conversational_search/`.
- **Resourcing:** Roadmap assumes a cross-functional pod (backend, MLE, DS, DX writers) delivering sequential phases outlined above.

### AI/ML Considerations (if applicable)
#### Data Requirements
Nodes must ingest heterogeneous corpora (files, URLs, web search) enriched with metadata, store conversation histories for personalization, and capture user feedback/annotations for evaluation. Evaluation nodes rely on golden datasets with relevance labels, while synthetic data generation nodes create paraphrases/negatives to expand coverage.

#### Algorithm selection
Baseline algorithms combine dense vector retrieval with BM25 keyword search, fused via RRF (Reciprocal Rank Fusion) or weighted strategies. Re-ranking leverages cross-encoders or LLM checkers, while conversation understanding uses coreference resolution, intent classification, and topic shift detection. Generation nodes employ LLMs constrained by retrieved evidence with optional streaming transports.

#### Model performance requirements
- Ingestion throughput ≥ 500 documents/minute.
- Retrieval p95 latency ≤ 1.5 seconds.
- Generation p95 latency ≤ 4 seconds (GPU-backed LLM assumption).

## MARKET DEFINITION (for products or large features)
### Total Addressable Market
Primary consumers are Orcheo users building conversational retrieval applications across enterprise and consumer scenarios. This includes both internal teams and external customers who use Orcheo as their workflow orchestration platform, while bespoke vendor-managed stacks remain out of scope.

### Launch Exceptions
| Market | Status | Considerations & Summary |
|--------|--------|--------------------------|
| None | N/A | Package is a building block for all Orcheo users; no geo-dependent exclusions identified. |

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] Retrieval latency | p95 ≤ 1.5s to keep conversations responsive during hybrid retrieval |
| [Secondary] Generation latency | p95 ≤ 4s with citations attached for final responses |
| [Guardrail] Ingestion throughput | ≥ 500 documents/minute while maintaining retry semantics |

### Rollout Strategy
Roll out sequential phases that move from MVP ingestion/retrieval/generation to conversation features, production hardening, and ongoing research/operations. Each phase unlocks a distinct user outcome (experimentation, multi-turn quality, production readiness, continuous improvement) while keeping dependencies manageable.

### Experiment Plan (if applicable)
Evaluation is driven by RetrievalEvaluationNode, AnswerQualityEvaluationNode, LLMJudgeNode, and FailureAnalysisNode, enabling offline recall/NDCG checks plus LLM-as-a-judge answer assessment. Traffic experiments use ABTestingNode with holdouts for new retrieval/generation strategies once Phase 2 components land.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Research pods | Deliver MVP ingestion, query processing, retrieval, and generation loop for experimentation. |
| **Phase 2** | Early adopters | Layer conversation management, coreference resolution, clarification, and metadata enrichment. |
| **Phase 3** | Production teams | Ship quality, routing, optimization, and UX upgrades for production readiness. |
| **Phase 4** | Broad rollout | Continue evaluation, analytics, compliance, and feedback capabilities as incremental releases. |

## HYPOTHESIS & RISKS
- **Hypothesis:** Providing modular conversational search nodes with shared interfaces will cut graph assembly time by enabling plug-and-play ingestion, retrieval, and generation; confidence is medium pending adoption metrics.
- **Hypothesis:** Built-in guardrails will accelerate production rollouts because operations teams can observe, triage, and gate deployments; confidence is medium once Phase 3 components exist.
- **Risk:** Vector store and external connector support (e.g., Pinecone vs. LanceDB) may not match team expectations, slowing adoption until adapters land.
  - **Mitigation:** Prioritize adapter development based on early adopter surveys; provide abstract interface documentation so teams can contribute custom adapters while official support is in progress.
- **Risk:** Compliance/privacy requirements across regions could delay MemoryPrivacyNode and PolicyComplianceNode if legal guidance is late.
  - **Mitigation:** Initiate early partner reviews with legal/compliance teams; design nodes with configurable policy hooks so regional rules can be injected without code changes.

## APPENDIX
### Node Composition Patterns
1. **Basic RAG Pipeline:** DocumentLoader → Chunking → Indexer → VectorSearch → GroundedGenerator.
2. **Hybrid Search:** (VectorSearch + BM25Search) → HybridFusion → ReRanker → GroundedGenerator.
3. **Conversational Search:** ConversationState → QueryRewrite → CoreferenceResolver → VectorSearch → GroundedGenerator.
4. **Multi-hop Reasoning:** MultiHopPlanner → (QueryRewrite → VectorSearch)* → ContextCompressor → GroundedGenerator.
5. **Research Pipeline:** VectorSearch → RetrievalEvaluation + AnswerQualityEvaluation → FailureAnalysis.

### Node Granularity Decisions
- **DenseSearchNode** and **SparseSearchNode** stay separate for independent configuration/benchmarking.
- **HybridFusionNode** remains explicit to support experimentation with fusion strategies.
- **ChunkingStrategyNode** is separate from DocumentLoaderNode for independent chunking research.
- **QueryClassifierNode** powers conditional branching without embedding logic inside retrievers.
