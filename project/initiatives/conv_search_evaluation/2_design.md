# Design Document

## For Conversational Search Evaluation (QReCC + MultiDoc2Dial)

- **Version:** 0.1
- **Author:** ShaojieJiang
- **Date:** 2026-02-09
- **Status:** Approved

---

## Overview

This design describes Orcheo evaluation workflows for conversational search on two complementary academic benchmarks: **QReCC** for query rewriting quality and **MultiDoc2Dial** for grounded generation. Together they cover the two core capabilities of the conversational search pipeline — rewriting and generation — each evaluated with the dataset best suited for it. The primary goal is to verify that Orcheo's workflow engine can reliably orchestrate end-to-end evaluation pipelines and to establish the first baseline metrics within the Orcheo ecosystem.

The evaluation is implemented as complete Orcheo workflows — the same execution model as any other Orcheo workflow. Dataset-specific data loading and metrics computation are implemented as registered nodes in the new `orcheo.nodes.evaluation` subpackage, which consolidates existing evaluation infrastructure (DatasetNode, RetrievalEvaluationNode, AnswerQualityEvaluationNode) with new composable metric nodes. This means evaluation workflows can be run locally during development or uploaded to a remote Orcheo server for long-running jobs, with no separate scripts or orchestration code. See the [requirements document](1_requirements.md) for dataset details, split choices, and metric rationale.

## Components

### Module Refactor: `orcheo.nodes.evaluation`

All evaluation nodes — both existing and new — move from `orcheo.nodes.conversational_search.evaluation` to a new top-level subpackage at `orcheo.nodes.evaluation/`. This refactor is motivated by:

1. **Task-agnostic metrics**: The composable metric nodes (ROUGE, BLEU, SemanticSimilarity, TokenF1) work on any `(predicted, reference)` text pairs — nesting them under `conversational_search` creates a misleading import path.
2. **Generic evaluation infrastructure**: Existing nodes like DatasetNode, RetrievalEvaluationNode, LLMJudgeNode, and AnalyticsExportNode are already domain-agnostic.
3. **File size**: `conversational_search/evaluation.py` is ~1,100 lines with 12 classes; adding 7 more in a single file is not sustainable.

**New module layout:**

```
src/orcheo/nodes/evaluation/
├── __init__.py       # Public re-exports and __all__
├── datasets.py       # DatasetNode (moved), QReCCDatasetNode (new), MultiDoc2DialDatasetNode (new)
├── metrics.py        # RougeMetricsNode (new), BleuMetricsNode (new),
│                     # SemanticSimilarityMetricsNode (new), TokenF1MetricsNode (new),
│                     # RetrievalEvaluationNode (moved), AnswerQualityEvaluationNode (moved)
├── batch.py          # ConversationalBatchEvalNode (new)
├── judges.py         # LLMJudgeNode (moved), ABTestingNode (moved),
│                     # FailureAnalysisNode (moved)
├── feedback.py       # UserFeedbackCollectionNode (moved), FeedbackIngestionNode (moved),
│                     # DataAugmentationNode (moved)
├── compliance.py     # PolicyComplianceNode (moved), MemoryPrivacyNode (moved),
│                     # TurnAnnotationNode (moved)
└── analytics.py      # AnalyticsExportNode (moved)
```

**Backward compatibility:** `orcheo.nodes.conversational_search.__init__` keeps re-exports from `orcheo.nodes.evaluation` so existing imports continue to work. The old `conversational_search/evaluation.py` file is deleted after the migration.

### New Nodes

- **QReCCDatasetNode** (`evaluation/datasets.py`) — Extends DatasetNode to parse QReCC conversation files. Extracts conversation history, raw queries, and gold rewrites per turn. Validates data against known quality issues in some splits. Loads QReCC data from Hugging Face.

- **MultiDoc2DialDatasetNode** (`evaluation/datasets.py`) — Extends DatasetNode to parse MultiDoc2Dial conversation files and grounding span annotations. Extracts gold responses and grounding spans. Loads MultiDoc2Dial data from Hugging Face.

- **ConversationalBatchEvalNode** (`evaluation/batch.py`) — Iterates conversations and turns through a configurable `StateGraph` pipeline sub-graph. Maintains conversation history across turns, collects per-turn predictions alongside gold labels, compiles the sub-graph once, and reuses the compiled runnable across turns. Requires an upstream dataset and a per-turn pipeline graph configured via workflow.

- **RougeMetricsNode** (`evaluation/metrics.py`) — Computes configurable ROUGE scores (`rouge-score`) between predicted and reference texts. Supports any ROUGE variant (`rouge1`, `rouge2`, `rougeL`, `rougeLsum`) and measure (`precision`, `recall`, `fmeasure`) via node attributes. Aggregates into per-item and corpus-level summaries. Task-agnostic: works on any `(predicted, reference)` text pairs.

- **BleuMetricsNode** (`evaluation/metrics.py`) — Computes SacreBLEU (`sacrebleu`) between predicted and reference texts. Aggregates into per-item and corpus-level summaries. Task-agnostic: works on any `(predicted, reference)` text pairs.

- **SemanticSimilarityMetricsNode** (`evaluation/metrics.py`) — Computes embedding-based cosine similarity between predicted and reference texts using commercial embedding APIs (OpenAI, Cohere, etc.) via LangChain's embedding interface. Configurable embedding model via node attributes. Aggregates into per-item and corpus-level summaries. Task-agnostic: works on any `(predicted, reference)` text pairs.

- **TokenF1MetricsNode** (`evaluation/metrics.py`) — Computes token-level precision, recall, and F1 between predicted and reference texts. Uses whitespace tokenization with optional normalization. Aggregates into per-item and corpus-level summaries. Task-agnostic: works on any `(predicted, reference)` text pairs.

### New Workflows

- **MultiDoc2Dial Corpus Indexer**
  - DocumentLoaderNode → ChunkingStrategyNode → ChunkEmbeddingNode → VectorStoreUpsertNode
  - Indexes the ~488-document MultiDoc2Dial corpus into the configured vector store; completes in minutes
  - Requires: MultiDoc2Dial documents, embedding model, vector store

- **QReCC Evaluation**
  - QReCCDatasetNode → ConversationalBatchEvalNode(pipeline=`StateGraph(rewrite)`) → [RougeMetricsNode(variant=rouge1, measure=recall), SemanticSimilarityMetricsNode] → AnalyticsExportNode
  - End-to-end rewriting evaluation in a single invocation
  - Metric nodes run in parallel branches and results are merged by AnalyticsExportNode
  - QueryRewriteNode is LLM-powered and handles coreference resolution
  - Configurable: rewrite model, similarity model, max conversations

- **MultiDoc2Dial Evaluation**
  - MultiDoc2DialDatasetNode → ConversationalBatchEvalNode(pipeline=`StateGraph(rewrite → search → compress → generate)`) → [TokenF1MetricsNode, BleuMetricsNode, RougeMetricsNode(variant=rougeL)] → AnalyticsExportNode
  - End-to-end generation evaluation in a single invocation
  - Metric nodes run in parallel branches and results are merged by AnalyticsExportNode
  - Accepts custom pipeline configs for comparing alternative pipeline configurations
  - Configurable: embedding model, generator model, max conversations

## Request Flows

### Flow 1: QReCC Evaluation Run

1. User runs QReCC evaluation workflow (locally or on Orcheo server)
2. QReCCDatasetNode loads and parses QReCC conversations with gold rewrites
3. ConversationalBatchEvalNode iterates conversations and turns:
   a. For each conversation, initializes empty history
   b. For each turn, feeds raw query and history into QueryRewriteNode
   c. Collects predicted rewrite and pairs with gold rewrite
   d. Updates conversation history with the turn
4. Metric nodes run in parallel:
   a. RougeMetricsNode (configured for ROUGE-1 Recall) computes lexical overlap scores
   b. SemanticSimilarityMetricsNode computes embedding-based similarity scores
5. AnalyticsExportNode merges metric results and produces per-conversation and corpus-level summaries

### Flow 2: MultiDoc2Dial Corpus Indexing

1. User runs corpus indexing workflow (locally or on Orcheo server)
2. DocumentLoaderNode loads the ~488 documents
3. ChunkingStrategyNode splits documents into passage-level chunks
4. ChunkEmbeddingNode generates dense embeddings
5. VectorStoreUpsertNode persists vectors to configured store
6. Indexing completes in minutes; final document and chunk counts reported

### Flow 3: MultiDoc2Dial Evaluation Run

1. User runs MultiDoc2Dial evaluation workflow (locally or on Orcheo server)
2. MultiDoc2DialDatasetNode loads and parses conversations with gold responses
3. ConversationalBatchEvalNode iterates conversations and turns:
   a. For each conversation, initializes empty history
   b. For each turn, feeds query and history through the compiled pipeline graph (rewrite → search → compress → generate)
   c. Collects generated response and pairs with gold response
   d. Updates conversation history with the turn
4. Metric nodes run in parallel:
   a. TokenF1MetricsNode computes token-level F1 scores
   b. BleuMetricsNode computes SacreBLEU scores
   c. RougeMetricsNode (configured for ROUGE-L) computes longest common subsequence overlap scores
5. AnalyticsExportNode merges metric results and produces per-conversation and corpus-level summaries

### Flow 4: Baseline Report Generation

1. User runs both evaluation workflows (sequentially or in parallel)
2. Each workflow produces its metric summaries via AnalyticsExportNode
3. Baseline report generated from combined metric output with aggregate metrics and per-conversation breakdowns

## API Contracts

### QReCCDatasetNode (`evaluation/datasets.py`)

```python
@registry.register(NodeMetadata(
    name="QReCCDatasetNode",
    description="Load QReCC conversations with gold rewrites for evaluation",
    category="evaluation",
))
class QReCCDatasetNode(DatasetNode):
    """Loads QReCC conversations and gold rewrites."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Parse QReCC data and return structured conversations."""
        ...
```

### MultiDoc2DialDatasetNode (`evaluation/datasets.py`)

```python
@registry.register(NodeMetadata(
    name="MultiDoc2DialDatasetNode",
    description="Load MultiDoc2Dial conversations with gold responses for evaluation",
    category="evaluation",
))
class MultiDoc2DialDatasetNode(DatasetNode):
    """Loads MultiDoc2Dial conversations, documents, and grounding spans."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Parse MultiDoc2Dial data and return structured conversations."""
        ...
```

### Composable Metric Nodes (`evaluation/metrics.py`)

All metric nodes follow a uniform contract: they read `predictions` and `references` (lists of text pairs) from upstream state and write their scores to a namespaced key in the output. This makes them freely composable — any workflow can wire in whichever metrics it needs.

```python
@registry.register(NodeMetadata(
    name="RougeMetricsNode",
    description="Compute ROUGE scores between predicted and reference texts",
    category="evaluation",
))
class RougeMetricsNode(TaskNode):
    """Configurable ROUGE scoring. Task-agnostic."""

    variant: str = Field(default="rouge1", description="rouge1, rouge2, rougeL, or rougeLsum")
    measure: str = Field(default="fmeasure", description="precision, recall, or fmeasure")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return per-item scores and corpus-level aggregate."""
        ...


@registry.register(NodeMetadata(
    name="BleuMetricsNode",
    description="Compute SacreBLEU between predicted and reference texts",
    category="evaluation",
))
class BleuMetricsNode(TaskNode):
    """Corpus-level and per-item BLEU scoring. Task-agnostic."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return per-item scores and corpus-level aggregate."""
        ...


@registry.register(NodeMetadata(
    name="SemanticSimilarityMetricsNode",
    description="Compute embedding cosine similarity between predicted and reference texts",
    category="evaluation",
))
class SemanticSimilarityMetricsNode(TaskNode):
    """Embedding-based similarity scoring. Task-agnostic."""

    model: str = Field(default="text-embedding-3-small", description="Embedding model (e.g. text-embedding-3-small, embed-english-v3.0)")
    dimensions: int = Field(default=512, description="Embedding dimension size")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return per-item scores and corpus-level aggregate."""
        ...


@registry.register(NodeMetadata(
    name="TokenF1MetricsNode",
    description="Compute token-level F1 between predicted and reference texts",
    category="evaluation",
))
class TokenF1MetricsNode(TaskNode):
    """Token-overlap precision, recall, and F1. Task-agnostic."""

    normalize: bool = Field(default=True, description="Lowercase and strip punctuation before scoring")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return per-item scores and corpus-level aggregate."""
        ...
```

**Uniform output contract** — every metric node returns:

```python
{
    "metric_name": str,          # e.g. "rouge1_recall", "sacrebleu", "semantic_similarity", "token_f1"
    "corpus_score": float,       # aggregate over all items
    "per_item": list[float],     # one score per (prediction, reference) pair
}
```

AnalyticsExportNode merges results from parallel metric branches by collecting each node's `metric_name` → `corpus_score` into a single metrics dict.

### Data Models

```python
class QreccConversation(BaseModel):
    conversation_id: str
    turns: list[QreccTurn]

class QreccTurn(BaseModel):
    turn_id: str
    raw_question: str
    gold_rewrite: str
    context: list[str]  # prior conversation turns
    gold_answer: str

class MD2DConversation(BaseModel):
    conversation_id: str
    domain: str  # e.g., "ssa", "va", "studentaid", "dmv"
    turns: list[MD2DTurn]

class MD2DTurn(BaseModel):
    turn_id: str
    user_utterance: str
    gold_response: str
    grounding_spans: list[GroundingSpan]

class GroundingSpan(BaseModel):
    doc_id: str
    span_text: str
    start: int
    end: int
```

### Workflow Execution

```bash
# QReCC evaluation (local server, default)
orcheo workflow upload examples/evaluation/qrecc_eval.py --config-file config.json
orcheo workflow run <workflow-id>

# QReCC evaluation (remote server)
orcheo workflow upload examples/evaluation/qrecc_eval.py --config-file config.json --server https://orcheo.example.com
orcheo workflow run <workflow-id> --server https://orcheo.example.com

# MultiDoc2Dial corpus indexing (local server, default)
orcheo workflow upload examples/evaluation/md2d_indexing.py --config-file config.json
orcheo workflow run <workflow-id>

# MultiDoc2Dial evaluation (local server, default)
orcheo workflow upload examples/evaluation/md2d_eval.py --config-file config.json
orcheo workflow run <workflow-id>

# MultiDoc2Dial evaluation (remote server)
orcheo workflow upload examples/evaluation/md2d_eval.py --config-file config.json --server https://orcheo.example.com
orcheo workflow run <workflow-id> --server https://orcheo.example.com
```

### Metric Output Schema

Each metric node produces a uniform output (see API Contracts above). AnalyticsExportNode merges results from all metric branches into the final report. The merged output varies only by which metric nodes the workflow wires in — adding or removing a metric requires no schema changes.

**QReCC** (RougeMetricsNode + SemanticSimilarityMetricsNode):

```json
{
  "dataset": "qrecc",
  "metrics": {
    "rouge1_recall": 0.78,
    "semantic_similarity": 0.85
  },
  "per_conversation": {
    "conv_1": {"rouge1_recall": 0.81, "semantic_similarity": 0.87},
    "conv_2": {"rouge1_recall": 0.75, "semantic_similarity": 0.83}
  },
  "config": {
    "rewrite_model": "gpt-4o-mini",
    "similarity_model": "text-embedding-3-small",
    "similarity_dimensions": 512
  }
}
```

**MultiDoc2Dial** (TokenF1MetricsNode + BleuMetricsNode + RougeMetricsNode):

```json
{
  "dataset": "multidoc2dial",
  "metrics": {
    "token_f1": 0.42,
    "sacrebleu": 18.5,
    "rougeL_fmeasure": 0.38
  },
  "per_conversation": {
    "conv_1": {"token_f1": 0.45, "sacrebleu": 20.1, "rougeL_fmeasure": 0.40},
    "conv_2": {"token_f1": 0.39, "sacrebleu": 16.8, "rougeL_fmeasure": 0.35}
  },
  "config": {
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 512,
    "generator_model": "gpt-4o-mini"
  }
}
```

## Data Models / Schemas

### QReCC Conversation Schema

| Field | Type | Description |
|-------|------|-------------|
| conversation_id | string | QReCC conversation identifier |
| turns | array[QreccTurn] | Ordered conversation turns |

### QReCC Turn Schema

| Field | Type | Description |
|-------|------|-------------|
| turn_id | string | Turn identifier within the conversation |
| raw_question | string | Original conversational question (may contain coreferences) |
| gold_rewrite | string | Human-written self-contained rewrite |
| context | array[string] | Prior conversation turns for context |
| gold_answer | string | Gold answer (used for context, not evaluation) |

### MultiDoc2Dial Conversation Schema

| Field | Type | Description |
|-------|------|-------------|
| conversation_id | string | Conversation identifier |
| domain | string | Domain (ssa, va, studentaid, dmv) |
| turns | array[MD2DTurn] | Ordered conversation turns |

### MultiDoc2Dial Turn Schema

| Field | Type | Description |
|-------|------|-------------|
| turn_id | string | Turn identifier within the conversation |
| user_utterance | string | User query |
| gold_response | string | Gold grounded response |
| grounding_spans | array[GroundingSpan] | Document spans the response is grounded in |

### Evaluation Result Schema

| Field | Type | Description |
|-------|------|-------------|
| dataset | string | Dataset identifier (qrecc or multidoc2dial) |
| metrics | object | Aggregate metrics |
| per_conversation | object | Per-conversation metric breakdowns |
| config | object | Full pipeline configuration snapshot (model versions, parameters) |

## Security Considerations

- **API keys:** Embedding model and LLM API keys managed through Orcheo secret bindings (no keys in config files or scripts).
- **Output files:** Metric reports contain only scores and configuration metadata; no sensitive content.
- **Corpus storage:** Vector store credentials follow existing Orcheo security patterns.

## Performance Considerations

- **QReCC evaluation:** Test split has 16,451 turns across 2,775 conversations. Each turn only requires a rewriting call and metric computation — no retrieval. Rewriting throughput depends on LLM API rate limits. For quick iteration, the workflow config supports a `max_conversations` parameter to evaluate a subset.
- **MultiDoc2Dial corpus indexing:** ~488 documents. At typical ingestion rates, completes in under 10 minutes on any vector store (including cloud services like Pinecone and MongoDB Atlas).
- **MultiDoc2Dial evaluation:** Validation split has 4,201 queries across 661 dialogues. Each query requires retrieval + generation. Target: < 1 hour for full evaluation. The workflow config supports a `max_conversations` parameter for quick iteration.
- **Caching:** Embedding computations cached to avoid redundant API calls across runs. Rewrite predictions cached so metric computation can be re-run without re-calling the LLM.

## Testing Strategy

Tests for the new `orcheo.nodes.evaluation` subpackage live under `tests/nodes/evaluation/`, mirroring the source layout. Existing tests under `tests/nodes/conversational_search/test_evaluation_nodes.py` are migrated to the new location as part of the refactor.

```
tests/nodes/evaluation/
├── test_datasets.py      # DatasetNode (migrated), QReCCDatasetNode, MultiDoc2DialDatasetNode
├── test_metrics.py       # RougeMetricsNode, BleuMetricsNode, SemanticSimilarityMetricsNode,
│                         # TokenF1MetricsNode, RetrievalEvaluationNode (migrated),
│                         # AnswerQualityEvaluationNode (migrated)
├── test_batch.py         # ConversationalBatchEvalNode
├── test_judges.py        # LLMJudgeNode (migrated), ABTestingNode (migrated),
│                         # FailureAnalysisNode (migrated)
├── test_feedback.py      # UserFeedbackCollectionNode (migrated), FeedbackIngestionNode (migrated),
│                         # DataAugmentationNode (migrated)
├── test_compliance.py    # PolicyComplianceNode (migrated), MemoryPrivacyNode (migrated),
│                         # TurnAnnotationNode (migrated)
└── test_analytics.py     # AnalyticsExportNode (migrated)
```

- **Unit tests:** QReCCDatasetNode parsing; MultiDoc2DialDatasetNode parsing; each composable metric node independently — RougeMetricsNode (all variant/measure combinations), BleuMetricsNode, SemanticSimilarityMetricsNode, and TokenF1MetricsNode — with known inputs and expected scores.
- **Integration tests:** End-to-end QReCC evaluation workflow on a micro-dataset (5 conversations) verifying correct metric computation. End-to-end MultiDoc2Dial evaluation workflow on a micro-corpus (10 documents, 5 conversations) verifying indexing, retrieval, generation, and metric computation.
- **Validation tests:** Verify that metric nodes produce correct scores on known inputs with pre-computed expected values (e.g. hand-checked ROUGE, BLEU, F1 for a handful of examples).
- **Manual QA checklist:**
  - [ ] QReCC conversations load correctly with gold rewrites
  - [ ] QReCC evaluation produces valid rewrite predictions and metrics
  - [ ] MultiDoc2Dial documents index successfully
  - [ ] MultiDoc2Dial evaluation produces valid generation output and metrics
  - [ ] Metrics are computed correctly and reported in the expected output format
  - [ ] Custom pipeline config evaluation produces valid results
  - [ ] Subset mode (max_conversations config) completes within 5 minutes for both datasets
  - [ ] Workflow uploads and runs successfully on remote Orcheo server
  - [ ] Backward-compatible imports from `orcheo.nodes.conversational_search` still resolve correctly

## Rollout Plan

Phasing follows the [requirements document](1_requirements.md#launchrollout-plan). QReCC ships first (no indexing dependency), followed by MultiDoc2Dial (requires corpus indexing). All deliverables ship as self-contained examples under `examples/evaluation/`.

## Open Issues

No open issues at this time.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-09 | ShaojieJiang | Initial draft |
