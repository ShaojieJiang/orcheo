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

### Node Overview Summary

The following table provides a quick reference of all proposed nodes organized by category and priority:

| Category | Node | Priority | Purpose |
|----------|------|----------|---------|
| **Data Ingestion** | DocumentLoaderNode | P1 | Load and normalize documents from various sources |
| | ChunkingStrategyNode | P1 | Apply configurable chunking strategies for optimal indexing |
| | MetadataExtractorNode | P1 | Extract structured metadata to enrich chunks |
| | EmbeddingIndexerNode | P1 | Generate embeddings and write to vector stores |
| | IncrementalIndexerNode | P2 | Handle delta updates without full reindexing |
| | SyncMonitorNode | P2 | Monitor ingestion pipeline health |
| **Retrieval** | VectorRetrieverNode | P1 | Dense vector similarity search |
| | BM25RetrieverNode | P1 | Traditional keyword-based retrieval |
| | HybridFusionNode | P1 | Merge results from multiple retrievers |
| | WebSearchNode | P1 | Integrate live web search results |
| | ReRankerNode | P2 | Apply cross-encoder reranking |
| | SourceRouterNode | P2 | Route queries to appropriate knowledge sources |
| **Query Processing** | QueryRewriteNode | P1 | Expand/rewrite queries using conversation context |
| | CoreferenceResolverNode | P1 | Resolve pronouns and references |
| | QueryClassifierNode | P1 | Classify query intent for routing |
| | ContextCompressorNode | P1 | Deduplicate and compress context |
| **Conversation** | ConversationStateNode | P1 | Maintain dialog state and history |
| | ConversationHistoryCompressorNode | P1 | Compress long conversation histories |
| | TopicShiftDetectorNode | P1 | Detect conversation topic changes |
| | MemorySummarizerNode | P2 | Summarize histories into episodic memory |
| | SessionManagementNode | P2 | Handle session lifecycle and isolation |
| **Generation** | GroundedGeneratorNode | P1 | Generate answers with citations |
| | QueryClarificationNode | P1 | Generate clarifying questions |
| | StreamingGeneratorNode | P2 | Token-by-token streaming responses |
| | HallucinationGuardNode | P2 | Validate answers against facts |
| | CitationsFormatterNode | P2 | Format citations for UI |
| **Planning & Routing** | MultiHopPlannerNode | P2 | Plan multi-step retrieval tasks |
| | FollowUpClassifierNode | P2 | Determine next action in conversation |
| **Caching & Optimization** | AnswerCachingNode | P2 | Cache similar query results |
| **Evaluation** | RetrievalEvaluationNode | P3 | Compute retrieval metrics (Recall@k, MRR, NDCG) |
| | AnswerQualityEvaluationNode | P3 | LLM-as-a-judge answer evaluation |
| | TurnAnnotationNode | P3 | Capture success/intent labels |
| | SyntheticJudgeNode | P3 | Automated answer evaluation |
| | DataAugmentationNode | P3 | Generate synthetic training data |
| | FailureAnalysisNode | P3 | Categorize and analyze failures |
| **Analytics** | UserFeedbackCollectionNode | P3 | Collect implicit/explicit feedback |
| | FeedbackIngestionNode | P3 | Ingest user feedback |
| | ABTestingNode | P3 | Support A/B testing workflows |
| | TelemetryExportNode | P3 | Export OpenTelemetry data |
| | AnalyticsExportNode | P3 | Export analytics to data warehouses |
| **Compliance** | PolicyComplianceNode | P3 | Enforce content filters and policies |
| | MemoryPrivacyNode | P3 | Apply redaction and retention policies |

**Priority Legend**: P1 = Essential (MVP), P2 = Production-Ready, P3 = Research & Operations

### Detailed Node Specifications

The nodes are organized into three priority tiers to guide implementation:

### Priority 1: Essential Nodes (MVP for conversational search research)

These nodes form the minimal viable conversational search loop and should be implemented first.

#### Data Ingestion
- **DocumentLoaderNode**: Accepts file blobs or URLs, normalizes into chunked `Document` objects, and emits metadata (source, mime type, checksum).
- **ChunkingStrategyNode**: Applies configurable chunking strategies (fixed-size, semantic, sentence-based, sliding window) to documents. Supports overlap configuration and metadata preservation. Essential for indexing quality experimentation.
- **MetadataExtractorNode**: Extracts structured metadata from documents (title, date, author, section hierarchy, document type). Enriches chunks with contextual information for improved retrieval.
- **EmbeddingIndexerNode**: Consumes normalized documents, batches them, computes embeddings (configurable model), and writes to a vector store interface (`BaseVectorStore`). Must support upsert semantics.

#### Retrieval & Ranking
- **VectorRetrieverNode**: Queries vector stores using dense embeddings. Supports configurable similarity metrics (cosine, dot product, euclidean) and top-k selection.
- **BM25RetrieverNode**: Performs traditional keyword-based retrieval using BM25/Lucene. Essential for low-cost baseline experiments and handling keyword-heavy queries.
- **HybridFusionNode**: Merges results from multiple retrievers (vector + BM25) using configurable fusion strategies (RRF - Reciprocal Rank Fusion, weighted scoring, or learned fusion). Critical for optimal retrieval performance.
- **WebSearchNode**: Integrates live web search APIs (e.g., Google, Bing, SerpAPI) to augment retrieved knowledge with fresh web content. Returns normalized search results compatible with vector store outputs. Essential for hybrid retrieval experiments and accessing fresh information.

#### Query Processing
- **QueryRewriteNode**: Expands or rewrites user queries using conversational context to improve recall (synonym expansion, entity resolution, language normalization) before retrieval runs.
- **CoreferenceResolverNode**: Resolves pronouns and references in conversational context ("it", "that document", "the previous one") to explicit entities. Essential for multi-turn conversations where users reference prior context.
- **QueryClassifierNode**: Classifies query intent and type (factual, navigational, clarification needed, multi-hop) to route to appropriate retrieval strategies. Enables conditional workflow branching.
- **ContextCompressorNode**: Deduplicates and compresses context while preserving citations. Critical for working within token limits during research experimentation.

#### Conversation Management
- **ConversationStateNode**: Maintains dialog state (turn history, entity store, user profile). Pluggable persistence (Redis, Postgres, in-memory) with TTL management.
- **ConversationHistoryCompressorNode**: Compresses long conversation histories while preserving key information. Uses summarization or selective retention strategies to manage token budgets in multi-turn dialogs.
- **TopicShiftDetectorNode**: Detects when conversation topic changes to trigger context reset or new search sessions. Prevents irrelevant prior context from polluting current queries.

#### Answer Generation
- **GroundedGeneratorNode**: Invokes LLMs with retrieved context, enforces citation attachment, and emits confidence scores.
- **QueryClarificationNode**: Generates clarifying questions when query ambiguity is detected. Prevents incorrect assumptions and improves answer accuracy through user interaction.

### Priority 2: Production-Ready Enhancements

These nodes add robustness, quality, and scalability for production deployments.

#### Query Planning & Routing
- **SourceRouterNode**: Chooses among heterogeneous knowledge sources (vector stores, scalar/BM25 indexes, web search, graph stores) and fuses their results based on confidence and freshness signals.
- **MultiHopPlannerNode**: Breaks complex user intents into ordered retrieval/generation steps and emits sub-task directives for downstream nodes.

#### Retrieval & Ranking
- **ReRankerNode**: Applies LLM or cross-encoder re-ranking; configurable top-k, threshold, and fallback modes. Valuable for production quality but not required for basic research prototypes.

#### Quality & Grounding
- **HallucinationGuardNode**: Validates generated answers against retrieved facts using entailment or rule-based checks; routes to fallback strategies when confidence < threshold.
- **CitationsFormatterNode**: Produces structured references (URL, title, snippet) suitable for UI consumption.

#### Conversation Flow
- **FollowUpClassifierNode**: Determines whether the next action is retrieval, clarification, or final answer. Useful for production but simple heuristics suffice for research.

#### Memory & Optimization
- **MemorySummarizerNode**: Periodically summarizes long histories into episodic memory slots stored via `BaseMemoryStore`.
- **AnswerCachingNode**: Caches semantically similar queries and their answers to reduce latency and LLM costs. Uses configurable similarity thresholds and TTL policies.
- **SessionManagementNode**: Handles session lifecycle events (creation, timeout, cleanup), manages multi-user session isolation, and enforces resource limits per session.

#### User Experience
- **StreamingGeneratorNode**: Extends GroundedGeneratorNode to support token-by-token streaming responses for real-time user experience. Emits partial results via async iterators. UX enhancement rather than research necessity.

#### Data Ingestion Monitoring
- **SyncMonitorNode**: Emits status events for ingestion pipelines (success/failure counts, retry schedules).
- **IncrementalIndexerNode**: Handles delta/incremental updates to existing indexes. Detects document changes (add/update/delete) and efficiently updates vector stores without full reindexing.

### Priority 3: Research, Compliance & Operations

These nodes support evaluation, compliance, and production operations but are not required for core conversational search functionality.

#### Evaluation & Research
- **RetrievalEvaluationNode**: Computes standard retrieval metrics (Recall@k, MRR, NDCG, MAP) given ground truth relevance labels. Essential for systematic retrieval quality assessment.
- **AnswerQualityEvaluationNode**: Evaluates generated answers using LLM-as-a-judge or rule-based metrics (faithfulness, relevance, completeness). Supports both reference-based and reference-free evaluation.
- **TurnAnnotationNode**: Captures structured success/intent labels (e.g., answer quality, follow-up need) either from human feedback loops or scripted heuristics and emits them to evaluation stores.
- **SyntheticJudgeNode**: Runs LLM-based evaluators on generated answers vs. references to support offline experimentation and regression gating.
- **DataAugmentationNode**: Generates synthetic training data (query variations, negative samples, paraphrases) for model fine-tuning and evaluation dataset expansion.
- **FailureAnalysisNode**: Identifies and categorizes failure modes in retrieval and generation (no results, irrelevant results, hallucinations, formatting errors). Emits structured failure reports for systematic improvement.

#### Tooling & Integration
- **UserFeedbackCollectionNode**: Collects both implicit (click-through, dwell time, reformulation) and explicit (thumbs up/down, ratings, comments) user feedback signals for evaluation and model improvement.
- **FeedbackIngestionNode**: Accepts explicit user feedback (thumbs up/down, free-form text) and writes to analytics sinks.
- **ABTestingNode**: Supports A/B testing of different retrieval or generation configurations. Routes traffic, tracks variant assignments, and exports comparison metrics.
- **TelemetryExportNode**: Exposes OpenTelemetry spans/metrics with node-level attributes (latency, token usage, result quality).
- **AnalyticsExportNode**: Exports structured analytics data (query patterns, performance metrics, user behavior) to data warehouses or analysis tools for offline research.

#### Compliance & Security
- **PolicyComplianceNode**: Enforces content filters (PII, toxicity) with configurable policies and audit logging.
- **MemoryPrivacyNode**: Applies configurable redaction and retention policies to stored dialog state to meet regional compliance requirements before persistence.

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

## Architecture Considerations

### Node Composition Patterns
The conversational search nodes are designed to compose into flexible workflows:

1. **Basic RAG Pipeline**: DocumentLoader → Chunking → Indexer → VectorRetriever → GroundedGenerator
2. **Hybrid Search**: (VectorRetriever + BM25Retriever) → HybridFusion → ReRanker → GroundedGenerator
3. **Conversational Search**: ConversationState → QueryRewrite → CoreferenceResolver → Retrieval → GroundedGenerator
4. **Multi-hop Reasoning**: MultiHopPlanner → (QueryRewrite → Retrieval)* → ContextCompressor → GroundedGenerator
5. **Research Pipeline**: Retrieval → RetrievalEvaluation + AnswerQualityEvaluation → FailureAnalysis

### Node Granularity Decisions

Some capabilities are intentionally separated for flexibility:

- **VectorRetrieverNode** and **BM25RetrieverNode** are separate to allow independent configuration and benchmarking
- **HybridFusionNode** is explicit rather than embedded in retrievers to support experimentation with fusion strategies
- **ChunkingStrategyNode** is separate from DocumentLoader to enable chunking strategy research without re-loading documents
- **QueryClassifierNode** enables conditional workflow branching based on query type

Nodes can be combined in implementations where separation isn't needed for a specific use case.

## Implementation Recommendations

### Phase 1: MVP (Weeks 1-4)
**Goal**: Enable basic conversational search research

Core retrieval loop:
1. **Data Ingestion**: DocumentLoaderNode, ChunkingStrategyNode, EmbeddingIndexerNode
2. **Query Processing**: QueryRewriteNode, ContextCompressorNode
3. **Retrieval**: VectorRetrieverNode, BM25RetrieverNode, HybridFusionNode
4. **Generation**: GroundedGeneratorNode

This minimal set enables:
- Document ingestion and indexing
- Hybrid retrieval experimentation
- Basic answer generation with citations
- Query rewriting research

### Phase 2: Conversational Features (Weeks 5-8)
**Goal**: Add conversation-aware capabilities

Add conversation handling:
1. **Conversation Management**: ConversationStateNode, ConversationHistoryCompressorNode
2. **Advanced Query Processing**: CoreferenceResolverNode, QueryClassifierNode, TopicShiftDetectorNode
3. **Clarification**: QueryClarificationNode
4. **External Knowledge**: WebSearchNode
5. **Metadata**: MetadataExtractorNode

This phase enables:
- Multi-turn conversation handling
- Reference resolution ("it", "that document")
- Ambiguity handling through clarification
- Fresh information via web search

### Phase 3: Quality & Production (Weeks 9-12)
**Goal**: Production-ready quality improvements

Add quality and robustness:
1. **Ranking**: ReRankerNode
2. **Routing**: SourceRouterNode, MultiHopPlannerNode
3. **Quality Gates**: HallucinationGuardNode, CitationsFormatterNode
4. **Optimization**: AnswerCachingNode, IncrementalIndexerNode
5. **UX**: StreamingGeneratorNode

### Phase 4: Research & Operations (Ongoing)
**Goal**: Enable systematic improvement

Add evaluation and analytics:
1. **Evaluation**: RetrievalEvaluationNode, AnswerQualityEvaluationNode, FailureAnalysisNode
2. **Data Generation**: DataAugmentationNode
3. **Feedback**: UserFeedbackCollectionNode, ABTestingNode
4. **Analytics**: TelemetryExportNode, AnalyticsExportNode
5. **Compliance**: PolicyComplianceNode, MemoryPrivacyNode

### Key Dependencies

```
Phase 1 (MVP)
└─ Phase 2 (Conversational)
   └─ Phase 3 (Production Quality)
      └─ Phase 4 (Research & Ops)

Parallel tracks after Phase 1:
- Evaluation nodes (Phase 4) can be built alongside Phase 2-3
- Compliance nodes can be added as needed
```

### Technical Priorities

1. **Interfaces First**: Define `BaseRetriever`, `BaseVectorStore`, `BaseMemoryStore` abstractions before node implementations
2. **Composability**: Each node should be independently testable and configurable
3. **Evaluation Early**: Build RetrievalEvaluationNode in Phase 2 to measure progress
4. **Incremental Complexity**: Start with rule-based/simple approaches, then add ML-based variants

## Open Questions
1. Which vector store adapters must be supported in v1 (e.g., Pinecone, PGVector, LanceDB, Chroma)?
2. Preferred hallucination detection approach (LLM judge vs. rule-based)?
3. Data retention requirements for stored conversation history across geographies.
4. Which external search/graph connectors are most valuable for the initial SourceRouterNode targets?
5. What golden datasets or heuristics should SyntheticJudgeNode rely on for consistent offline evaluation?
6. Should coreference resolution use rule-based (SpaCy) or neural approaches (NeuralCoref)?
7. What fusion strategies should HybridFusionNode prioritize (RRF, weighted sum, learned models)?
8. How should topic shift detection balance sensitivity vs. false positives in conversation flow?
