# PRD: Conversational Search Node Package

## METADATA
- **Authors:** Shaojie Jiang
- **Project/Feature Name:** Conversational Search Node Package
- **Type:** Product
- **Summary:** Reusable package of graph-ready Orcheo nodes covering ingestion, retrieval, ranking, grounding, and answer generation for conversational search workflows where users issue natural-language queries across heterogeneous knowledge.
- **Owner (if different than authors):** TBD
- **Date Started:** TBD

## RELEVANT LINKS & STAKEHOLDERS
_[Include only the documents relevant to your project/feature scope]_

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Prior Artifacts | [Roadmap](../roadmap.md) | PM | TBD |
| Design Review | [This document](requirements.md) | PM | TBD |
| Design File/Deck | TBD | Designer | TBD |
| Eng Requirement Doc | TBD | Tech Lead | TBD |
| Marketing Requirement Doc (if applicable) | N/A | PMM | N/A |
| Experiment Plan (if applicable) | TBD | DS | TBD |
| Rollout Docs (if applicable) | TBD | Product Ops | TBD |

## PROBLEM DEFINITION
### Objectives
Deliver a cohesive package of conversational search nodes that lets builders compose ingestion, retrieval, grounding, and generative steps without bespoke glue code. Provide observability hooks and guardrails so production teams can operate and iterate on conversational agents confidently.

### Target users
Graph builders, applied researchers, and operations engineers who assemble conversational search workflows inside Orcheo. They need modular components to ingest data, search heterogeneous sources, craft responses, and monitor deployed agents.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Workflow builder | Drop in nodes for ingestion, chunking, retrieval, fusion, and generation | I can launch conversational search experiments without rewriting infrastructure | P0 | DocumentLoaderNode, ChunkingStrategyNode, EmbeddingIndexerNode, VectorRetrieverNode, BM25RetrieverNode, HybridFusionNode, and GroundedGeneratorNode available with configs |
| Retrieval researcher | Swap retrievers, rankers, and planners while reusing shared interfaces | I can benchmark new strategies quickly | P0 | Base abstractions for retrievers/vector stores/memory plus configurable nodes that are independently testable |
| Operations lead | Enable observability, guardrails, and compliance across conversations | I can safely run conversational agents in production | P1 | Guard nodes (HallucinationGuardNode, PolicyComplianceNode), and session/memory controls exposed |

### Context, Problems, Opportunities
Teams currently hand-roll conversational search flows, creating duplicated work, inconsistent abstractions, and limited observability. There is an opportunity to standardize on Orcheo nodes that cover ingestion through evaluation, expose configuration-first APIs, and make it trivial to plug different vendors, memory stores, or retrievers into a conversation-aware loop.

### Product goals and Non-goals
**Goals:** Provide modular nodes for conversational search, ensure composability through shared interfaces, and bake in guardrails that ease production operations.
**Non-goals:** Custom UI surfaces, data labeling tooling, or vendor-specific orchestration beyond the defined node contracts remain out of scope.

## PRODUCT DEFINITION
### Requirements
Conversational search functionality will live under `orcheo.nodes.conversational_search`, along with shared utilities (schema validators) and the docs/examples needed for adoption. Requirements are split between core conversational search (Priority 0/1) and research, compliance, and operations (Priority 2).

#### Node Overview Summary
| Category | Node | Priority | Purpose |
|----------|------|----------|---------|
| **Data Ingestion** | DocumentLoaderNode | P0 | Load and normalize documents from various sources |
| | ChunkingStrategyNode | P0 | Apply configurable chunking strategies for optimal indexing |
| | MetadataExtractorNode | P0 | Extract structured metadata to enrich chunks |
| | EmbeddingIndexerNode | P0 | Generate embeddings and write to vector stores |
| | IncrementalIndexerNode | P1 | Handle delta updates without full reindexing |
| | SyncMonitorNode | P1 | Monitor ingestion pipeline health |
| **Retrieval** | VectorRetrieverNode | P0 | Dense vector similarity search |
| | BM25RetrieverNode | P0 | Traditional keyword-based retrieval |
| | HybridFusionNode | P0 | Merge results from multiple retrievers |
| | WebSearchNode | P0 | Integrate live web search results |
| | ReRankerNode | P1 | Apply cross-encoder reranking |
| | SourceRouterNode | P1 | Route queries to appropriate knowledge sources |
| **Query Processing** | QueryRewriteNode | P0 | Expand/rewrite queries using conversation context |
| | CoreferenceResolverNode | P0 | Resolve pronouns and references |
| | QueryClassifierNode | P0 | Classify query intent for routing |
| | ContextCompressorNode | P0 | Deduplicate and compress context |
| **Conversation** | ConversationStateNode | P0 | Maintain dialog state and history |
| | ConversationHistoryCompressorNode | P0 | Compress long conversation histories |
| | TopicShiftDetectorNode | P0 | Detect conversation topic changes |
| | MemorySummarizerNode | P1 | Maintain episodic memory beyond the current turn |
| **Generation & Guardrails** | GroundedGeneratorNode | P0 | Generate grounded answers with citations |
| | StreamingGeneratorNode | P1 | Stream token-by-token responses |
| | HallucinationGuardNode | P1 | Validate answers vs. retrieved facts |
| | CitationsFormatterNode | P1 | Emit structured citations for UIs |
| | QueryClarificationNode | P1 | Solicit clarifying information before answering |
| **Memory & Optimization** | AnswerCachingNode | P1 | Cache responses for repeated or similar questions |
| | SessionManagementNode | P1 | Handle session lifecycle and resource limits |
| | MultiHopPlannerNode | P1 | Support planned multi-hop retrieval |
| **Observability & Compliance** | PolicyComplianceNode | P1 | Enforce content filters |
| | MemoryPrivacyNode | P1 | Apply redaction/retention policies |
| | SyncMonitorNode | P1 | Emit ingestion health metrics |
| **Evaluation & Tooling** | RetrievalEvaluationNode | P2 | Measure recall, MRR, NDCG, MAP |
| | AnswerQualityEvaluationNode | P2 | Score generated answers |
| | TurnAnnotationNode | P2 | Capture structured annotations |
| | SyntheticJudgeNode | P2 | Run LLM evaluators |
| | DataAugmentationNode | P2 | Generate synthetic training data |
| | FailureAnalysisNode | P2 | Categorize failure modes |
| | UserFeedbackCollectionNode | P2 | Collect implicit/explicit feedback |
| | FeedbackIngestionNode | P2 | Persist feedback to sinks |
| | ABTestingNode | P2 | Manage experiment traffic |
| | AnalyticsExportNode | P2 | Export analytics data |

#### Priority 0/1: Core Conversational Search
**Data Ingestion**
- **DocumentLoaderNode:** Connectors for file, web, and API sources with format normalization.
- **ChunkingStrategyNode:** Configurable character/token rules with overlap control for optimal indexing.
- **MetadataExtractorNode:** Attaches structured metadata (title, source, tags) powering filters and ranking.
- **EmbeddingIndexerNode:** Runs embedding models, writes to supported vector stores, and validates schema.
- **IncrementalIndexerNode:** Delta-sync pipeline that detects adds/updates/deletes without full reindexing.
- **SyncMonitorNode:** Emits ingestion telemetry (success, error, retry counts) for observability dashboards.

**Query Processing & Conversation**
- **ConversationStateNode:** Maintains per-session context, participants, and runtime state objects.
- **ConversationHistoryCompressorNode:** Summarizes long histories with token budgets for downstream nodes.
- **TopicShiftDetectorNode:** Flags when queries diverge enough to warrant search resets.
- **QueryRewriteNode:** Uses conversation memories to rewrite or expand user questions.
- **CoreferenceResolverNode:** Resolves pronouns/entities for precise retrieval.
- **QueryClassifierNode:** Routes queries (search vs. clarifying question vs. finalization) using classifiers.
- **ContextCompressorNode:** Deduplicates retrieved context and enforces token budgets.
- **QueryClarificationNode:** Requests additional details from the user when intent is ambiguous.

**Retrieval & Ranking**
- **VectorRetrieverNode:** Dense similarity search built atop the base vector store abstraction.
- **BM25RetrieverNode:** Keyword retrieval for sparse/deterministic matching.
- **HybridFusionNode:** Weighted/RRF fusion layer merging retriever outputs.
- **WebSearchNode:** Optional live search for freshness.
- **ReRankerNode:** Cross-encoder or LLM scoring pipeline for top-k results.
- **SourceRouterNode:** Chooses the right knowledge source via heuristics or learned models.
- **MultiHopPlannerNode:** Plans sequential retrieval hops when questions require decomposition.

**Generation & Guardrails**
- **GroundedGeneratorNode:** Core generative responder that cites retrieved context.
- **StreamingGeneratorNode:** Streams responses via async iterators for responsive UX.
- **HallucinationGuardNode:** Validates responses using entailment or rule-based checks with fallback routing.
- **CitationsFormatterNode:** Produces structured reference payloads (URL, title, snippet).

**Memory, Optimization, and Operations**
- **MemorySummarizerNode:** Writes episodic memory back into `BaseMemoryStore` for personalization.
- **AnswerCachingNode:** Caches semantically similar Q&A pairs with TTL and similarity policies.
- **SessionManagementNode:** Controls lifecycle, concurrency, and cleanup for session workloads.
- **PolicyComplianceNode & MemoryPrivacyNode:** Enforce content, retention, and redaction policies aligned with compliance requirements.

#### Priority 2: Research, Compliance & Operations
These nodes support evaluation, compliance, and production operations but are not required for core conversational search functionality.

**Evaluation & Research**
- **RetrievalEvaluationNode:** Computes Recall@k, MRR, NDCG, MAP using relevance labels.
- **AnswerQualityEvaluationNode:** Scores answers via LLM-as-a-judge or rule-based metrics (faithfulness, relevance, completeness).
- **TurnAnnotationNode:** Captures structured success/intent labels from human or heuristic sources.
- **SyntheticJudgeNode:** Runs LLM evaluators on answers vs. references for offline experimentation and regression gating.
- **DataAugmentationNode:** Generates synthetic training data (query variations, negatives, paraphrases) for fine-tuning and evaluation.
- **FailureAnalysisNode:** Categorizes failure modes (no results, irrelevant results, hallucinations, formatting errors) and emits reports.

**Tooling & Integration**
- **UserFeedbackCollectionNode:** Collects implicit (clicks, reformulations) and explicit (thumbs, ratings) feedback.
- **FeedbackIngestionNode:** Persists explicit feedback to analytics sinks for aggregation.
- **ABTestingNode:** Routes traffic between configurations, tracks variant assignments, and exports comparison metrics.
- **AnalyticsExportNode:** Sends structured analytics data (query patterns, performance metrics, user behavior) to warehouses or research tools.

**Compliance & Security**
- **PolicyComplianceNode:** Enforces content filters (PII, toxicity) with configurable policies and audit logging.
- **MemoryPrivacyNode:** Applies configurable redaction and retention policies to stored dialog state per regional requirements.

#### Implementation Roadmap
##### Phase 1: MVP (Weeks 1-4)
**Goal:** Enable basic conversational search research.
Core retrieval loop: DocumentLoaderNode, ChunkingStrategyNode, EmbeddingIndexerNode, QueryRewriteNode, ContextCompressorNode, VectorRetrieverNode, BM25RetrieverNode, HybridFusionNode, and GroundedGeneratorNode.

##### Phase 2: Conversational Features (Weeks 5-8)
**Goal:** Add conversation-aware capabilities.
Add conversation handling (ConversationStateNode, ConversationHistoryCompressorNode), advanced query processing (CoreferenceResolverNode, QueryClassifierNode, TopicShiftDetectorNode), clarification (QueryClarificationNode), and metadata enrichment (MetadataExtractorNode, WebSearchNode).

##### Phase 3: Quality & Production (Weeks 9-12)
**Goal:** Deliver production-ready quality improvements.
Add ranking (ReRankerNode), routing (SourceRouterNode, MultiHopPlannerNode), quality gates (HallucinationGuardNode, CitationsFormatterNode), optimization (AnswerCachingNode, IncrementalIndexerNode), and UX (StreamingGeneratorNode).

##### Phase 4: Research & Operations (Ongoing)
**Goal:** Enable systematic improvement.
Add evaluation (RetrievalEvaluationNode, AnswerQualityEvaluationNode, FailureAnalysisNode), data generation (DataAugmentationNode), feedback (UserFeedbackCollectionNode, ABTestingNode), analytics (AnalyticsExportNode), and compliance (PolicyComplianceNode, MemoryPrivacyNode).

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
- MkDocs reference page summarizing configuration tables and usage notes.
- Automated unit tests per node and an integration test for a reference conversational search graph.

### Designs (if applicable)
No dedicated UI designs; relies on node reference docs and example graphs. Figma artifacts TBD as UI or orchestration surfaces emerge.

### Other Teams Impacted
- **Docs & Education:** Requires coordination for MkDocs reference pages and adoption guides.
- **Security & Compliance:** PolicyComplianceNode and MemoryPrivacyNode demand alignment with security/legal reviews.

## TECHNICAL CONSIDERATIONS
_[The goal of this section is to outline the high level engineering requirement to facilitate the engineering resource planning. Detailed engineering requirements or system design is out of scope for this section.]_

### Architecture Overview
Conversational search nodes plug into Orcheo graphs as modular steps for ingestion, retrieval, planning, generation, and observability. Each node exposes a typed `NodeConfig`, shares telemetry and tracing contracts, and interoperates with shared abstractions (vector stores, memory stores, message buses). The package also ships reference graphs plus schema validators demonstrating how flows connect.

### Technical Requirements
- **Configurability:** Every node exposes validated configs with documented defaults and schema enforcement.
- **Observability:** Nodes integrate with Orcheo telemetry, emitting structured events, correlation IDs, and health metrics (e.g., SyncMonitorNode).
- **Error Handling:** Implement graceful retries with exponential backoff for transient failures via `NodeResult.status` semantics.
- **Performance Targets:** Meet ingestion throughput (≥ 500 docs/minute), retrieval p95 latency (≤ 1.5s), and generation p95 latency (≤ 4s) assuming GPU-backed LLMs.
- **Security:** Nodes handling credentials rely on Orcheo secret bindings and redact sensitive values in logs/storage.
- **Testing:** Provide unit tests per node plus integration coverage for a reference conversational search graph located under `tests/nodes/conversational_search/`.
- **Resourcing:** Roadmap assumes a cross-functional pod (backend, MLE, DS, DX writers) delivering sequential phases outlined above.

### AI/ML Considerations (if applicable)
#### Data Requirements
Nodes must ingest heterogeneous corpora (files, URLs, web search) enriched with metadata, store conversation histories for personalization, and capture user feedback/annotations for evaluation. Evaluation nodes rely on golden datasets with relevance labels, while synthetic data generation nodes create paraphrases/negatives to expand coverage.

#### Algorithm selection
Baseline algorithms combine dense vector retrieval with BM25 keyword search, fused via RRF or weighted strategies. Re-ranking leverages cross-encoders or LLM checkers, while conversation understanding uses coreference resolution, intent classification, and topic shift detection. Generation nodes employ LLMs constrained by retrieved evidence with optional streaming transports.

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
| [Guardrail] Ingestion throughput | ≥ 500 documents/minute while maintaining observability and retry semantics |

### Rollout Strategy
Roll out sequential phases that move from MVP ingestion/retrieval/generation to conversation features, production hardening, and ongoing research/operations. Each phase unlocks a distinct user outcome (experimentation, multi-turn quality, production readiness, continuous improvement) while keeping dependencies manageable.

### Experiment Plan (if applicable)
Evaluation is driven by RetrievalEvaluationNode, AnswerQualityEvaluationNode, SyntheticJudgeNode, and FailureAnalysisNode, enabling offline recall/NDCG checks plus LLM-as-a-judge answer assessment. Traffic experiments use ABTestingNode with holdouts for new retrieval/generation strategies once Phase 2 components land.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Research pods (Weeks 1-4) | Deliver MVP ingestion, query processing, retrieval, and generation loop for experimentation. |
| **Phase 2** | Early adopters (Weeks 5-8) | Layer conversation management, coreference resolution, clarification, and metadata enrichment. |
| **Phase 3** | Production teams (Weeks 9-12) | Ship quality, routing, optimization, and UX upgrades for production readiness. |
| **Phase 4** | Broad rollout (Ongoing) | Continue evaluation, analytics, compliance, and feedback capabilities as incremental releases. |

## HYPOTHESIS & RISKS
_[Each hypothesis/risk should be limited to 2-3 sentences (i.e., one sentence for hypothesis, one sentence for confidence in hypothesis). Generally, PRDs should be focused on validating a single hypothesis and no more than two hypotheses.]_
_[Hypothesis: what do you believe to be true, and what do you think will happen if you are correct? Recommend framing your hypothesis in a customer-centric way, while also describing how the user problem impacts metrics.]_
_[Risk: what are potential risk areas for this feature and what could be some unintended consequences?]_
- **Hypothesis:** Providing modular conversational search nodes with shared interfaces will cut graph assembly time by enabling plug-and-play ingestion, retrieval, and generation; confidence is medium pending adoption metrics.
- **Hypothesis:** Built-in guardrails will accelerate production rollouts because operations teams can observe, triage, and gate deployments; confidence is medium once Phase 3 components exist.
- **Risk:** Vector store and external connector support (e.g., Pinecone vs. LanceDB) may not match team expectations, slowing adoption until adapters land.
- **Risk:** Compliance/privacy requirements across regions could delay MemoryPrivacyNode and PolicyComplianceNode if legal guidance is late; mitigation involves early partner reviews.

## APPENDIX
### Node Composition Patterns
1. **Basic RAG Pipeline:** DocumentLoader → Chunking → Indexer → VectorRetriever → GroundedGenerator.
2. **Hybrid Search:** (VectorRetriever + BM25Retriever) → HybridFusion → ReRanker → GroundedGenerator.
3. **Conversational Search:** ConversationState → QueryRewrite → CoreferenceResolver → Retrieval → GroundedGenerator.
4. **Multi-hop Reasoning:** MultiHopPlanner → (QueryRewrite → Retrieval)* → ContextCompressor → GroundedGenerator.
5. **Research Pipeline:** Retrieval → RetrievalEvaluation + AnswerQualityEvaluation → FailureAnalysis.

### Node Granularity Decisions
- **VectorRetrieverNode** and **BM25RetrieverNode** stay separate for independent configuration/benchmarking.
- **HybridFusionNode** remains explicit to support experimentation with fusion strategies.
- **ChunkingStrategyNode** is separate from DocumentLoaderNode for independent chunking research.
- **QueryClassifierNode** powers conditional branching without embedding logic inside retrievers.

### Open Questions
1. Which vector store adapters must be supported in v1 (e.g., Pinecone, PGVector, LanceDB, Chroma)?
2. Preferred hallucination detection approach (LLM judge vs. rule-based)?
3. Data retention requirements for stored conversation history across geographies.
4. Which external search/graph connectors are most valuable for the initial SourceRouterNode targets?
5. What golden datasets or heuristics should SyntheticJudgeNode rely on for consistent offline evaluation?
6. Should coreference resolution use rule-based (SpaCy) or neural approaches (NeuralCoref)?
7. What fusion strategies should HybridFusionNode prioritize (RRF, weighted sum, learned models)?
8. How should topic shift detection balance sensitivity vs. false positives in conversation flow?
