# Project Plan

## For Conversational Search Evaluation (QReCC + MultiDoc2Dial)

- **Version:** 0.1
- **Author:** ShaojieJiang
- **Date:** 2026-02-09
- **Status:** Approved

---

## Overview

Execution plan to build Orcheo evaluation workflows on QReCC (query rewriting) and MultiDoc2Dial (grounded generation), and establish reproducible baselines for the community. Each milestone builds incrementally: evaluation module refactor first, then shared metrics infrastructure, QReCC rewriting evaluation, MultiDoc2Dial generation evaluation, and finally documentation and reporting.

**Related Documents:**
- Requirements: [PRD: Conv Search Evaluation](1_requirements.md)
- Design: [Design Document](2_design.md)

---

## Milestones

### Milestone 0: Evaluation Module Refactor

**Description:** Move all existing evaluation nodes from `orcheo.nodes.conversational_search.evaluation` to a new top-level `orcheo.nodes.evaluation/` subpackage. This unblocks clean placement of new nodes and establishes the module structure described in the [design document](2_design.md#module-refactor-orcheonodesevaluation). Success criteria: all existing evaluation nodes relocated to their target files; all existing tests migrated to `tests/nodes/evaluation/`; backward-compatible re-exports in `orcheo.nodes.conversational_search.__init__`; `make lint` and `make test` pass with zero regressions.

#### Task Checklist

- [x] Task 0.1: Create `src/orcheo/nodes/evaluation/` subpackage with `__init__.py`
  - Dependencies: None
- [x] Task 0.2: Move DatasetNode to `evaluation/datasets.py`
  - Dependencies: Task 0.1
- [x] Task 0.3: Move RetrievalEvaluationNode and AnswerQualityEvaluationNode to `evaluation/metrics.py`
  - Dependencies: Task 0.1
- [x] Task 0.4: Move LLMJudgeNode, ABTestingNode, and FailureAnalysisNode to `evaluation/judges.py`
  - Dependencies: Task 0.1
- [x] Task 0.5: Move UserFeedbackCollectionNode, FeedbackIngestionNode, and DataAugmentationNode to `evaluation/feedback.py`
  - Dependencies: Task 0.1
- [x] Task 0.6: Move PolicyComplianceNode, MemoryPrivacyNode, and TurnAnnotationNode to `evaluation/compliance.py`
  - Dependencies: Task 0.1
- [x] Task 0.7: Move AnalyticsExportNode to `evaluation/analytics.py`
  - Dependencies: Task 0.1
- [x] Task 0.8: Update `orcheo.nodes.evaluation.__init__` with all public re-exports
  - Dependencies: Tasks 0.2–0.7
- [x] Task 0.9: Add backward-compatible re-exports in `orcheo.nodes.conversational_search.__init__` pointing to `orcheo.nodes.evaluation`
  - Dependencies: Task 0.8
- [x] Task 0.10: Migrate existing tests from `tests/nodes/conversational_search/test_evaluation_nodes.py` to `tests/nodes/evaluation/` (split by module)
  - Dependencies: Task 0.8
- [x] Task 0.11: Delete `orcheo/nodes/conversational_search/evaluation.py` and verify `make lint && make test` pass
  - Dependencies: Tasks 0.9–0.10

---

### Milestone 1: Shared Infrastructure & Metrics

**Description:** Establish the shared evaluation scaffolding, composable metric nodes, and example directory structure used by both QReCC and MultiDoc2Dial evaluations. Success criteria: all four composable metric nodes (RougeMetricsNode, BleuMetricsNode, SemanticSimilarityMetricsNode, TokenF1MetricsNode) implemented and independently unit-tested; example directory structure created with configuration templates.

#### Task Checklist

- [x] Task 1.1: Create example directory structure (`examples/evaluation/`) with shared configuration templates and data download instructions
  - Dependencies: Milestone 0
- [x] Task 1.2: Implement RougeMetricsNode (configurable variant and measure) in `evaluation/metrics.py` with unit tests in `tests/nodes/evaluation/test_metrics.py`
  - Dependencies: rouge-score package
- [x] Task 1.3: Implement BleuMetricsNode (SacreBLEU) in `evaluation/metrics.py` with unit tests in `tests/nodes/evaluation/test_metrics.py`
  - Dependencies: sacrebleu package
- [x] Task 1.4: Implement SemanticSimilarityMetricsNode (embedding cosine similarity) in `evaluation/metrics.py` with unit tests in `tests/nodes/evaluation/test_metrics.py`
  - Dependencies: LangChain embeddings, commercial embedding API access (e.g. OpenAI)
- [x] Task 1.5: Implement TokenF1MetricsNode (token-level precision/recall/F1) in `evaluation/metrics.py` with unit tests in `tests/nodes/evaluation/test_metrics.py`
  - Dependencies: None (pure Python tokenization)
- [x] Task 1.6: Implement metric output schema and report writer (JSON output, formatted tables)
  - Dependencies: Tasks 1.2–1.5

---

### Milestone 2: QReCC Query Rewriting Evaluation

**Description:** Implement QReCC data loading, the rewriting workflow, and the QReCC evaluation runner. This milestone requires no corpus indexing and can be completed quickly. Evaluates on the test split (2,775 conversations, 16,451 turns) which has publicly available gold rewrites. Success criteria: QReCC test conversations loaded with gold rewrites; QueryRewriteNode produces rewrite predictions; ROUGE-1 R and semantic similarity reported; baseline results established.

#### Task Checklist

- [x] Task 2.1: Implement QReCCDatasetNode in `evaluation/datasets.py` (parse conversations, gold rewrites, and conversation context) with unit tests in `tests/nodes/evaluation/test_datasets.py`
  - Dependencies: QReCC data files downloaded, Milestone 0
- [x] Task 2.2: Build QReCC rewriting workflow using QueryRewriteNode (which handles coreference resolution as part of the rewriting process); create config template
  - Dependencies: Task 2.1
- [x] Task 2.3: Implement ConversationalBatchEvalNode in `evaluation/batch.py` with unit tests in `tests/nodes/evaluation/test_batch.py`; build QReCC evaluation runner that iterates conversations/turns through the workflow, wires RougeMetricsNode (rouge1, recall) and SemanticSimilarityMetricsNode in parallel, and produces reports
  - Dependencies: Task 2.2, Milestone 1 metric nodes
- [x] Task 2.4: Add integration tests on a micro-dataset (5 conversations)
  - Dependencies: Tasks 2.1, 2.3

---

### Milestone 3: MultiDoc2Dial Grounded Generation Evaluation

**Description:** Implement MultiDoc2Dial data loading, corpus indexing, the generation workflow, and the MultiDoc2Dial evaluation runner. Evaluates on the validation split (661 dialogues, 4,201 queries) since test split gold labels are withheld. The pipeline runs each query through rewriting, dense retrieval, context compression, and grounded generation. Success criteria: ~488-document corpus indexed; pipeline produces responses on validation split; F1, SacreBLEU, ROUGE-L reported; baseline results established.

#### Task Checklist

- [x] Task 3.1: Implement MultiDoc2DialDatasetNode in `evaluation/datasets.py` (parse conversations, documents, grounding spans, and gold responses) with unit tests in `tests/nodes/evaluation/test_datasets.py`
  - Dependencies: MultiDoc2Dial data files downloaded, Milestone 0
- [x] Task 3.2: Build MultiDoc2Dial corpus indexing workflow (DocumentLoaderNode → ChunkingStrategyNode → ChunkEmbeddingNode → VectorStoreUpsertNode) for the ~488-document corpus
  - Dependencies: Task 3.1; vector store configured; embedding model access
- [x] Task 3.3: Build MultiDoc2Dial generation workflow with QueryRewriteNode → DenseSearchNode → ContextCompressorNode → GroundedGeneratorNode pipeline; create config template
  - Dependencies: Task 3.2 indexed corpus
- [x] Task 3.4: Build MultiDoc2Dial evaluation runner that iterates conversations/turns through the ConversationalBatchEvalNode, wires TokenF1MetricsNode, BleuMetricsNode, and RougeMetricsNode (rougeL) in parallel, and produces reports
  - Dependencies: Task 3.3, Milestone 1 metric nodes
- [x] Task 3.5: Add integration tests on a micro-corpus (10 documents, 5 conversations)
  - Dependencies: Tasks 3.1, 3.4

---

### Milestone 4: Documentation & Reporting

**Description:** Finalize documentation, generate baseline comparison reports, and validate reproducibility. Success criteria: comprehensive README with setup/run/interpret instructions; baseline metric tables for both datasets; reproducibility validated across repeated runs.

#### Task Checklist

- [x] Task 4.1: Write comprehensive README covering data download, setup, evaluation commands, and result interpretation for both QReCC and MultiDoc2Dial
  - Dependencies: Milestones 2-3 completed
- [x] Task 4.2: Build unified evaluation runner (`run_all`) that executes both QReCC and MultiDoc2Dial evaluations and produces a combined report
  - Dependencies: Milestones 2-3 evaluation runners
- [x] Task 4.3: Generate LaTeX-ready metric tables suitable for academic submission
  - Dependencies: Milestone 2-3 metric reports
- [x] Task 4.4: Run full regression and validate reproducibility (identical results across repeated runs)
  - Dependencies: All prior milestones

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-09 | ShaojieJiang | Initial draft |
