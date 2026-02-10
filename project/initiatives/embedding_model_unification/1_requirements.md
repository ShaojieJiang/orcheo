# Requirements Document

## METADATA
- **Authors:** Shaojie Jiang
- **Project/Feature Name:** Embedding Model Unification with Explicit Sparse Paths
- **Type:** Enhancement
- **Summary:** Replace dense embedding method registries with a unified `embed_model` + `model_kwargs` configuration across embedding-related nodes, while retaining sparse embeddings through explicit sparse-only configuration paths.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2026-02-10

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Prior Artifacts | `project/initiatives/conversational_search/design.md` | Eng | Conversational Search Design |
| Design Review | `project/initiatives/embedding_model_unification/2_design.md` | Eng | Embedding Unification Design |
| Engineering Requirements | `project/initiatives/embedding_model_unification/1_requirements.md` | Eng | This document |
| Rollout Docs | `project/initiatives/embedding_model_unification/3_plan.md` | Eng | Embedding Unification Plan |

## PROBLEM DEFINITION
### Objectives
- Standardize dense embedding model configuration across the codebase to a single contract (`embed_model`, `model_kwargs`) and remove node-specific dense embedding plumbing.
- Keep sparse embedding support for hybrid indexing, retrieval, and evaluation, but isolate it into explicit sparse-only contracts instead of mixed generic embedding APIs.

### Target users
Internal Orcheo engineers building and maintaining nodes, workflows, and examples.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Node developer | Configure dense embeddings with one consistent schema | I can add and debug dense retrieval/indexing nodes faster | P0 | Dense embedding nodes expose `embed_model` and `model_kwargs` instead of `embedding_method` variants |
| Maintainer | Keep sparse support only where needed | The code stays maintainable without breaking hybrid workflows | P0 | Sparse APIs are limited to sparse-capable nodes and hybrid paths |
| Workflow author (internal) | Use the same embedding configuration shape as AgentNode model config | I can reason about AI model setup consistently | P1 | Existing `examples/` are migrated to one dense embedding config pattern with clear dense/sparse lane boundaries |
| Evaluation engineer | Continue comparing dense-only vs hybrid variants | I can evaluate retrieval tradeoffs reliably | P1 | Existing hybrid evaluation workflow remains supported with explicit sparse configuration |

### Context, Problems, Opportunities
The current implementation mixes multiple embedding patterns: global registry methods, per-node method names, provider-specific conditionals, and sparse payload handling. This increases cognitive load, introduces repeated error handling, and spreads embedding concerns across many files.

Sparse embeddings are still needed in concrete paths:
- Hybrid indexing (dense + BM25 sparse) into Pinecone.
- Hybrid retrieval fan-out and fusion (dense + sparse + web).
- Evaluation workflows comparing dense-only vs hybrid variants.
- Pinecone upsert/query paths that use `sparse_values` / `sparse_vector`.

Because there are no external users yet, this is the right time for a breaking cleanup. Sparse functionality should still be retained through a cleaner architecture.

### Product Goals and Non-goals
Goals:
- Unify dense embedding configuration to `embed_model` and `model_kwargs` in embedding-capable nodes.
- Use `langchain.embeddings.init_embeddings` as the default initialization path.
- Keep sparse embedding support for hybrid use cases via explicit sparse contracts and dedicated sparse-capable nodes.
- Update tests, examples, and docs to match the new contract.

Non-goals:
- Backward compatibility for legacy dense fields (`embedding_method`, `embedding_methods`, provider-specific dense config variants).
- Removing hybrid dense+sparse indexing/retrieval demos.
- Introducing feature flags or dual runtime paths for old and new embedding contracts.

## PRODUCT DEFINITION
### Requirements
P0:
- Replace node attributes:
  - dense: `embedding_method` and provider-specific fields -> `embed_model` (+ `model_kwargs`)
  - sparse: explicit sparse config fields on sparse-capable nodes (for example, `sparse_model`, `sparse_kwargs`)
  - `ChunkEmbeddingNode`: replace mixed embedding map usage with separate `dense_embedding_specs` and `sparse_embedding_specs` maps
- Affected nodes include, at minimum:
  - `TextEmbeddingNode`
  - `IncrementalIndexerNode`
  - `DenseSearchNode`
  - `ChunkEmbeddingNode` (as multi-embedding producer for hybrid indexing)
  - `SparseSearchNode` (sparse-only path)
  - any additional node that initializes dense embeddings directly (for example semantic similarity metrics)
- Add a shared dense embedding initialization utility that wraps:
  - `init_embeddings(model=<embed_model>, **model_kwargs)`
  - invocation for single or batch text (`embed_query`, `embed_documents`, async variants)
- Add or retain a sparse embedding utility for supported sparse models (BM25/SPLADE style), used only by sparse-capable nodes.
- Remove mixed dense+sparse payload acceptance from dense-only paths; dense-only nodes should not accept sparse-only outputs.
- Remove `credential_env_vars` from dense embedding configuration paths.
- Pass credentials through `model_kwargs` so embedding initialization receives provider auth via the unified kwargs contract.

P1:
- Harmonize error messages across nodes for model initialization and embedding execution failures.
- Migrate existing `examples/` in this initiative to the new contract, including clear dense/sparse lane boundaries.

Out of scope:
- Introducing new sparse providers beyond currently supported BM25/SPLADE-style flows.

### Explicit Coverage Inventory

Nodes in scope (must be covered by implementation and tests):
- `ChunkEmbeddingNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- `TextEmbeddingNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- `IncrementalIndexerNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- `DenseSearchNode` (`src/orcheo/nodes/conversational_search/retrieval.py`)
- `SparseSearchNode` (`src/orcheo/nodes/conversational_search/retrieval.py`)
- `SemanticSimilarityMetricsNode` (`src/orcheo/nodes/evaluation/metrics.py`)

Examples/config/docs in scope (must be migrated if they use dense/sparse embedding models):
- Conversational search:
  - `examples/conversational_search/demo_1_hybrid_indexing/demo_1.py`
  - `examples/conversational_search/demo_1_hybrid_indexing/config.json`
  - `examples/conversational_search/demo_2_basic_rag/demo_2.py`
  - `examples/conversational_search/demo_3_hybrid_search/demo_3.py`
  - `examples/conversational_search/demo_3_hybrid_search/config.json`
  - `examples/conversational_search/demo_4_conversational/demo_4.py`
  - `examples/conversational_search/demo_5_production/demo_5.py`
  - `examples/conversational_search/demo_5_production/config.json`
  - `examples/conversational_search/demo_6_evaluation/demo_6.py`
  - `examples/conversational_search/demo_6_evaluation/config.json`
- Evaluation:
  - `examples/evaluation/md2d_indexing.py`
  - `examples/evaluation/md2d_eval.py`
  - `examples/evaluation/qrecc_eval.py`
  - `examples/evaluation/config_md2d_indexing.json`
  - `examples/evaluation/config_md2d.json`
  - `examples/evaluation/config_qrecc.json`
  - `examples/evaluation/README.md`
- MongoDB agent:
  - `examples/mongodb_agent/01_web_scrape_and_upload.py`
  - `examples/mongodb_agent/03_qa_agent.py`
  - `examples/mongodb_agent/config.json`
  - `examples/mongodb_agent/README.md`

### Design (if applicable)
- Design doc: `project/initiatives/embedding_model_unification/2_design.md`

### [Optional] Other Teams Impacted
- Backend/API: Node schema changes may impact workflow ingestion and execution payloads.
- Examples/docs maintainers: Must update conversational search and evaluation examples.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
Embedding-capable nodes call one shared dense embedding initializer and invoker using LangChain `init_embeddings`. Node schemas become consistent and no longer depend on global method registration for core paths.

### Technical Requirements
- `langchain>=1.1.3` already present; use `langchain.embeddings.init_embeddings`.
- Normalize model names to LangChain-compatible forms (for example `openai:text-embedding-3-small`).
- Migrate constants using incompatible prefixes (for example `embedding:openai:...`) where they represent dense models.
- Do not introduce a temporary alias translator for legacy dense model strings; migrate configs/constants directly.
- Keep sparse payload compatibility at vector-store boundaries where needed (`sparse_values`, `sparse_vector`).
- Ensure vector dimension consistency remains enforced at vector store boundaries.
- Ensure all changed nodes keep strict type hints and pass lint/type/test gates.

### AI/ML Considerations (if applicable)
#### Data Requirements
No new training data required. Inputs remain workflow texts and queries.

#### Algorithm Selection
Dense embedding providers supported by LangChain initialization are the default path.
Sparse retrieval remains supported for hybrid workloads through dedicated sparse encoders.

#### Model Performance Requirements
No regression in dense retrieval and semantic similarity behavior relative to current defaults.

## MARKET DEFINITION (for products or large features)
Not applicable. Internal platform refactor.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] Dense schema consistency | 100% of dense embedding nodes use `embed_model` + `model_kwargs` |
| [Primary] Sparse path continuity | 100% of hybrid index/search/evaluation examples still support sparse retrieval |
| [Secondary] Test health | Relevant unit/integration tests pass after migration |
| [Guardrail] Runtime errors | No new uncaught embedding initialization or execution error classes are introduced in tests for either lane |

### Rollout Strategy
Single breaking rollout in development branch, then merge after green CI. No staged compatibility path.

### Experiment Plan (if applicable)
Not applicable.

### Estimated Launch Phases (if applicable)

| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Dense lane | Refactor dense node schemas and runtime initialization |
| **Phase 2** | Sparse lane cleanup | Isolate sparse-specific contracts and remove mixed-path ambiguity |
| **Phase 3** | CI merge | Merge when lint/tests pass and docs are consistent |

## HYPOTHESIS & RISKS
Hypothesis: A clear dual-lane model (unified dense + explicit sparse) will reduce maintenance burden while preserving hybrid retrieval quality and evaluation coverage.
Risk: A dense refactor can accidentally break sparse hybrid flows if node boundaries are not explicit.
Risk Mitigation: Define sparse-capable node contracts explicitly, keep integration tests for hybrid demos, and validate vector-store sparse query/upsert behavior.

## APPENDIX
- Candidate migration map and file-level impacts are tracked in the design and plan docs.
