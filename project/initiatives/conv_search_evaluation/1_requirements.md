# PRD: Conversational Search Evaluation

## METADATA
- **Authors:** ShaojieJiang
- **Project/Feature Name:** Conversational Search Evaluation (QReCC + MultiDoc2Dial)
- **Type:** Enhancement
- **Summary:** Build Orcheo evaluation workflows for conversational search on two complementary benchmarks — QReCC for query rewriting and MultiDoc2Dial for grounded generation — and establish reproducible baselines for the community to reference and improve upon.
- **Owner:** Shaojie Jiang
- **Date Started:** 2026-02-09

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link |
|-----------|------|
| Prior Artifacts | [Conversational Search PRD](../conversational_search/requirements.md) |
| Design Review | [Conversational Search Design](../conversational_search/design.md) |
| Demo Suite | [Demo Plan](../conversational_search/demo_plan.md) |
| QReCC | [https://github.com/apple/ml-qrecc](https://github.com/apple/ml-qrecc) |
| MultiDoc2Dial | [https://github.com/IBM/multidoc2dial](https://github.com/IBM/multidoc2dial) |

## PROBLEM DEFINITION

### Objectives
Create Orcheo evaluation workflows for conversational search against two established academic benchmarks — QReCC for query rewriting quality and MultiDoc2Dial for grounded generation — and establish reproducible baselines that others can reference, reproduce, and improve upon.

### Target users
Researchers preparing academic publications, graph builders benchmarking pipeline strategies, and Orcheo evaluators seeking published baselines to compare against.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Researcher | Run query rewriting evaluation on QReCC with a single command | I can reproduce published baselines and compare Orcheo's rewriting quality against them | P0 | End-to-end Orcheo workflow that loads QReCC data, runs rewriting, and reports ROUGE-1 R and semantic similarity |
| Researcher | Run grounded generation evaluation on MultiDoc2Dial with a single command | I can reproduce published baselines and compare Orcheo's retrieval-to-generation pipeline against them | P0 | End-to-end Orcheo workflow that loads MultiDoc2Dial data, indexes the corpus, runs the generation pipeline, and reports F1, SacreBLEU, ROUGE-L |
| Graph builder | Run evaluation on my own pipeline configuration and compare against published baselines | I can measure how my pipeline performs on recognized benchmarks | P0 | Evaluation workflows accept custom pipeline configs and report standard metrics |
| Paper author | Generate metric tables from evaluation results | I can include results directly in an academic submission | P1 | LaTeX-ready metric tables for both datasets |

### Context, Problems, Opportunities
The existing conversational search demo suite covers functional workflows but lacks rigorous evaluation against recognized academic benchmarks. This initiative fills that gap by evaluating the two core capabilities of the conversational search pipeline — query rewriting and grounded generation — each with the dataset best suited for it.

**QReCC** (Anantha et al., NAACL 2021) provides 14K conversations with 81K turns, each annotated with human-written gold query rewrites. The test split (2,775 conversations, 16,451 turns) includes publicly available gold rewrites, enabling direct evaluation of rewriting quality without requiring any retrieval index. It is well-cited with published baselines from the SCAI-QReCC shared tasks (2021, 2022).

**MultiDoc2Dial** (Feng et al., EMNLP 2021) provides 4.5K conversations grounded in ~488 documents across four domains, with gold grounding span annotations. The test split gold labels are withheld for shared task evaluation, so we evaluate on the validation split (661 dialogues, 4,201 queries), which has full public annotations. The small corpus can be indexed in minutes on any vector store, making it practical for evaluating the full retrieval-to-generation pipeline without the infrastructure burden of large-scale indexing.

Together, these two datasets provide comprehensive coverage of the conversational search pipeline with minimal infrastructure requirements.

### Product goals and Non-goals
**Goals:**
- Create Orcheo evaluation workflows for query rewriting (QReCC) and grounded generation (MultiDoc2Dial).
- Establish reproducible evaluation baselines that serve as reference points for the community.
- Produce standard evaluation output with published metrics for both datasets.
- Provide well-documented examples that new users can run and extend with their own pipeline configurations.

**Non-goals:**
- Training or fine-tuning models on evaluation data.
- Building a custom evaluation UI or dashboard.
- Competing for state-of-the-art leaderboard positions.

## PRODUCT DEFINITION

### Requirements

#### Datasets

| Dataset | Source | Eval Split | Conversations | Turns/Queries | Corpus | Primary Focus | Orcheo Node Coverage |
|---------|--------|------------|---------------|---------------|--------|---------------|---------------------|
| **QReCC** | NAACL 2021 (Apple Research) | Test | 2,775 | 16,451 | None needed | Query rewriting quality | QueryRewriteNode |
| **MultiDoc2Dial** | EMNLP 2021 (IBM Research) | Validation* | 661 | 4,201 | ~488 documents | Grounded generation | DenseSearchNode, GroundedGeneratorNode, ContextCompressorNode |

*MultiDoc2Dial test split gold labels are withheld for shared task evaluation; the validation split is used instead.

#### Pipeline Workflows

**QReCC — Query Rewriting Workflow:**
Raw conversational query + history → QueryRewriteNode → Rewrite output

QueryRewriteNode is LLM-powered and handles coreference resolution as part of the rewriting process, eliminating the need for a separate coreference resolution stage.

**MultiDoc2Dial — Grounded Generation Workflow:**
QueryRewriteNode → DenseSearchNode → ContextCompressorNode → GroundedGeneratorNode

The pipeline runs each query through rewriting, dense retrieval, context compression, and grounded generation.

#### Metrics

**QReCC (query rewriting):**
- ROUGE-1 Recall — lexical overlap with gold rewrites
- Semantic Similarity — embedding-based similarity between predicted and gold rewrites

**MultiDoc2Dial (grounded generation):**
- F1 — token-level overlap with reference responses
- SacreBLEU — corpus-level translation-style metric
- ROUGE-L — longest common subsequence overlap

#### Deliverables
| Priority | Deliverable | Description |
|----------|-------------|-------------|
| P0 | QReCCDatasetNode | Node that loads and parses QReCC conversations and gold rewrites into evaluation-ready format |
| P0 | MultiDoc2DialDatasetNode | Node that loads and parses MultiDoc2Dial conversations, documents, and grounding annotations |
| P0 | MultiDoc2Dial corpus indexing workflow | Orcheo workflow to index the ~488-document corpus |
| P0 | RougeMetricsNode | Composable node that computes configurable ROUGE scores (any variant/measure) between predicted and reference texts |
| P0 | BleuMetricsNode | Composable node that computes SacreBLEU between predicted and reference texts |
| P0 | SemanticSimilarityMetricsNode | Composable node that computes embedding cosine similarity between predicted and reference texts |
| P0 | TokenF1MetricsNode | Composable node that computes token-level F1 between predicted and reference texts |
| P0 | QReCC evaluation workflow | End-to-end Orcheo workflow: data loading → batch rewriting → metrics → report |
| P0 | MultiDoc2Dial evaluation workflow | End-to-end Orcheo workflow: data loading → batch generation → metrics → report |
| P1 | Comparison report | Formatted metric tables and analysis narrative for both datasets |

### Designs (if applicable)
No dedicated UI designs; evaluation is delivered as Orcheo workflows that can be run locally or uploaded to a remote Orcheo server. Outputs are metric reports and tables suitable for paper inclusion.

## TECHNICAL CONSIDERATIONS

### Architecture Overview
The evaluation is implemented as complete Orcheo workflows, consistent with how all other Orcheo workflows are built and run. Dataset-specific data loading and metrics computation are implemented as registered nodes, following the established patterns from the existing evaluation node package (DatasetNode, RetrievalEvaluationNode, AnswerQualityEvaluationNode). This means evaluation workflows can be run locally during development or uploaded to a remote Orcheo server for long-running evaluation jobs — using the same execution model as any other workflow.

### Technical Requirements
- **Data access:** QReCC and MultiDoc2Dial datasets must be downloadable via public URLs or Hugging Face.
- **Indexing:** MultiDoc2Dial corpus (~488 documents) must be indexed using the existing ingestion pipeline (DocumentLoaderNode → ChunkingStrategyNode → ChunkEmbeddingNode → VectorStoreUpsertNode). Indexing completes in minutes.
- **Metrics implementation:** ROUGE-1 R, semantic similarity, F1, SacreBLEU, and ROUGE-L computation via standard NLP libraries (rouge-score, sacrebleu) and commercial embedding APIs (OpenAI, Cohere, etc.) via LangChain's embedding interface.
- **Reproducibility:** All configurations, random seeds, and model versions documented for exact reproduction.

### AI/ML Considerations

#### Data Requirements
- **QReCC:** Test split — 2,775 conversations, 16,451 turns with publicly available human-written gold rewrites. No retrieval corpus needed.
- **MultiDoc2Dial:** Validation split — 661 dialogues, 4,201 queries across ~488 documents (Social Security, VA, StudentAid, DMV domains) with gold responses and grounding span annotations. Test split gold labels are withheld.

#### Algorithm selection
QReCC evaluation compares predicted query rewrites against gold rewrites using lexical and semantic metrics — no retrieval is involved. MultiDoc2Dial evaluation uses dense retrieval (embedding similarity), context compression, and grounded generation. This mirrors the algorithms already implemented in the conversational search node package.

#### Model performance requirements
- QReCC rewriting metrics should be comparable to published SCAI-QReCC shared task baselines.
- MultiDoc2Dial generation metrics should be comparable to published DialDoc workshop baselines.
- QReCC test split evaluation (16,451 turns) should complete within minutes (no indexing required). MultiDoc2Dial validation split evaluation (4,201 queries) should complete within 1 hour including corpus indexing.

## LAUNCH/ROLLOUT PLAN

### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] Baseline establishment | Reference baselines published with standard metrics on both QReCC (ROUGE-1 R, semantic similarity) and MultiDoc2Dial (F1, SacreBLEU, ROUGE-L) |
| [Secondary] Baseline comparability | Results within expected range of published baselines for both datasets |
| [Guardrail] Reproducibility | Same configuration produces identical results across runs |

### Rollout Strategy
Ship as examples under `examples/evaluation/` alongside the existing demo suite. No feature flags required; these are self-contained evaluation workflows.

### Experiment Plan (if applicable)
Run both evaluation workflows (QReCC query rewriting, MultiDoc2Dial grounded generation) to produce reference baselines. Publish results so that others can reproduce them and use them as starting points for their own pipeline configurations.

## HYPOTHESIS & RISKS
- **Hypothesis:** Orcheo evaluation workflows on QReCC and MultiDoc2Dial can produce reproducible baselines within the expected range of published results, providing credible reference points for the community.
- **Risk:** QReCC has reported data quality issues on some Hugging Face splits (mismatched column structures).
  - **Mitigation:** Validate data integrity during loading; use the canonical GitHub release if Hugging Face splits are unreliable.
- **Risk:** MultiDoc2Dial's narrow domain (government services) may not generalize to all conversational search use cases.
  - **Mitigation:** Document domain limitations clearly; position MultiDoc2Dial as a grounded generation benchmark, not a general retrieval benchmark.

## APPENDIX

### Future Dataset Extensions
| Dataset | Size | Best for | Notes |
|---------|------|----------|-------|
| **TREC CAsT 2019** | 8.8M passages (MS MARCO-only, local index) | End-to-end retrieval with graded relevance | Gold-standard retrieval benchmark; requires local FAISS/LanceDB index |
| **TopiOCQA** | 25.7M passages | Topic-switching conversations | Interesting for topic shift detection; large corpus |
| **OR-QuAC** | 11–17M passages | Open-retrieval conversational QA | Wikipedia-based; extractive spans only |

CAsT 2019 is the recommended next dataset, using a local FAISS or LanceDB index with the 8.8M MS MARCO passages to evaluate end-to-end retrieval with graded relevance judgments.
