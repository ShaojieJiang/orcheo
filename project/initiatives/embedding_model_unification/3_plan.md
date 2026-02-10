# Project Plan

## Embedding Model Unification with Explicit Sparse Paths

- **Version:** 0.1
- **Author:** Shaojie Jiang
- **Date:** 2026-02-10
- **Status:** Approved

---

## Overview

This project replaces custom dense embedding method plumbing with a unified dense embedding configuration (`embed_model`, `model_kwargs`) and retains sparse embeddings through explicit sparse-only contracts. The work will be delivered as one breaking refactor across nodes, tests, and docs.

**Related Documents:**
- Requirements: `project/initiatives/embedding_model_unification/1_requirements.md`
- Design: `project/initiatives/embedding_model_unification/2_design.md`

---

## Explicit Migration Scope

### Nodes (must be migrated)

- [ ] `ChunkEmbeddingNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- [ ] `TextEmbeddingNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- [ ] `IncrementalIndexerNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- [ ] `DenseSearchNode` (`src/orcheo/nodes/conversational_search/retrieval.py`)
- [ ] `SparseSearchNode` (`src/orcheo/nodes/conversational_search/retrieval.py`)
- [ ] `SemanticSimilarityMetricsNode` (`src/orcheo/nodes/evaluation/metrics.py`)

### Examples/config/docs (must be migrated where embedding config is used)

- [ ] `examples/conversational_search/demo_1_hybrid_indexing/demo_1.py`
- [ ] `examples/conversational_search/demo_1_hybrid_indexing/config.json`
- [ ] `examples/conversational_search/demo_2_basic_rag/demo_2.py`
- [ ] `examples/conversational_search/demo_3_hybrid_search/demo_3.py`
- [ ] `examples/conversational_search/demo_3_hybrid_search/config.json`
- [ ] `examples/conversational_search/demo_4_conversational/demo_4.py`
- [ ] `examples/conversational_search/demo_5_production/demo_5.py`
- [ ] `examples/conversational_search/demo_5_production/config.json`
- [ ] `examples/conversational_search/demo_6_evaluation/demo_6.py`
- [ ] `examples/conversational_search/demo_6_evaluation/config.json`
- [ ] `examples/evaluation/md2d_indexing.py`
- [ ] `examples/evaluation/md2d_eval.py`
- [ ] `examples/evaluation/qrecc_eval.py`
- [ ] `examples/evaluation/config_md2d_indexing.json`
- [ ] `examples/evaluation/config_md2d.json`
- [ ] `examples/evaluation/config_qrecc.json`
- [ ] `examples/evaluation/README.md`
- [ ] `examples/mongodb_agent/01_web_scrape_and_upload.py`
- [ ] `examples/mongodb_agent/03_qa_agent.py`
- [ ] `examples/mongodb_agent/config.json`
- [ ] `examples/mongodb_agent/README.md`

---

## Milestones

### Milestone 1: Core runtime and schema refactor

**Description:** Introduce a shared dense embedding utility and migrate node schemas/runtime from `embedding_method` patterns to `embed_model` + `model_kwargs`.

#### Task Checklist

- [ ] Task 1.1: Add shared embedding initialization/execution helper wrapping `langchain.embeddings.init_embeddings`
  - Dependencies: None
- [ ] Task 1.2: Migrate conversational search nodes to unified embedding fields
  - Dependencies: Task 1.1
- [ ] Task 1.3: Migrate evaluation semantic similarity node to unified embedding fields
  - Dependencies: Task 1.1
- [ ] Task 1.4: Remove legacy dense registry-based embedding resolution in migrated paths
  - Dependencies: Task 1.2 and Task 1.3
- [ ] Task 1.5: Remove `credential_env_vars` from embedding configs and pass credentials through `model_kwargs`
  - Dependencies: Task 1.2 and Task 1.3
- [ ] Task 1.6: Migrate legacy dense model string constants/configs (for example `embedding:openai:...`) directly without adding a temporary alias translator
  - Dependencies: Task 1.4

---

### Milestone 2: Explicit sparse lane implementation

**Description:** Keep sparse embeddings for hybrid workflows but isolate sparse behavior into explicit sparse-capable node contracts.

#### Task Checklist

- [ ] Task 2.1: Define and implement sparse helper interfaces (`sparse_model`, `sparse_kwargs`) for sparse-capable nodes
  - Dependencies: Milestone 1
- [ ] Task 2.2: Refactor `SparseSearchNode` and hybrid indexing paths to use explicit sparse lane contracts
  - Dependencies: Task 2.1
- [ ] Task 2.3: Keep Pinecone sparse vector upsert/query paths and validate sparse payload boundaries in vector store adapters
  - Dependencies: Task 2.1
- [ ] Task 2.4: Remove dense-node acceptance of sparse-only outputs to enforce lane separation
  - Dependencies: Task 2.2
- [ ] Task 2.5: Update `ChunkEmbeddingNode` schema to separate `dense_embedding_specs` and `sparse_embedding_specs` maps
  - Dependencies: Task 2.1

---

### Milestone 3: Tests, docs, and validation

**Description:** Align tests and docs with the new contract and verify repository quality gates.

#### Task Checklist

- [ ] Task 3.1: Update unit/integration tests for new fields while preserving hybrid dense+sparse coverage
  - Dependencies: Milestone 1 and Milestone 2
- [ ] Task 3.2: Update all examples/config files to the new dense fields and explicit sparse fields where applicable
  - Dependencies: Milestone 1
- [ ] Task 3.3: Run quality gates (`make format`, `make lint`, targeted `uv run pytest ...`)
  - Dependencies: Task 3.1 and Task 3.2
- [ ] Task 3.4: Final editorial review of initiative docs (`1_requirements.md`, `2_design.md`, `3_plan.md`) for terminology consistency and clarity
  - Dependencies: Task 3.2

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-10 | Shaojie Jiang | Initial draft for dense model unification and explicit sparse-path rollout |
