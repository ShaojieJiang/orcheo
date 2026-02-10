# Design Document

## Embedding Model Unification with Explicit Sparse Paths

- **Version:** 0.1
- **Author:** Shaojie Jiang
- **Date:** 2026-02-10
- **Status:** Approved

---

## Overview

This refactor replaces custom conversational-search dense embedding registration and method resolution with a unified dense model contract used directly by nodes. Dense-capable nodes will declare `embed_model` and `model_kwargs`, then initialize embeddings via `langchain.embeddings.init_embeddings`.

Sparse embeddings will be retained for hybrid indexing/retrieval/evaluation, but moved behind explicit sparse-only contracts. The design is intentionally breaking for dense configuration fields, while preserving sparse functionality through clearer boundaries.

## Components

- **Node schema layer (`src/orcheo/nodes/...`)**
  - Responsibility: expose consistent embedding fields (`embed_model`, `model_kwargs`) in node attributes.
  - Dependencies: Pydantic models and workflow ingestion.

- **Embedding runtime utility (new shared helper)**
  - Responsibility: initialize dense embeddings from model string + kwargs and run query/document embeddings.
  - Dependencies: `langchain.embeddings.init_embeddings`.

- **Sparse embedding runtime utility**
  - Responsibility: initialize and invoke sparse encoders (BM25/SPLADE-style) for sparse-capable nodes only.
  - Dependencies: sparse encoder integrations (for example `pinecone_text`).

- **Conversational search nodes**
  - Responsibility: call dense helper for dense paths and sparse helper for sparse-only paths.
  - Dependencies: vector stores, node state extraction.

- **Evaluation metrics nodes**
  - Responsibility: switch provider-specific embedding creation to unified init path.
  - Dependencies: existing metric computation logic.

- **Docs/examples/tests**
  - Responsibility: update dense config references and keep sparse references only in hybrid contexts.

## Explicit Scope Inventory

### Node coverage

- `ChunkEmbeddingNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- `TextEmbeddingNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- `IncrementalIndexerNode` (`src/orcheo/nodes/conversational_search/ingestion.py`)
- `DenseSearchNode` (`src/orcheo/nodes/conversational_search/retrieval.py`)
- `SparseSearchNode` (`src/orcheo/nodes/conversational_search/retrieval.py`)
- `SemanticSimilarityMetricsNode` (`src/orcheo/nodes/evaluation/metrics.py`)

### Example/config coverage

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

## Request Flows

### Flow 1: Dense search query embedding

1. `DenseSearchNode` receives query text from state.
2. Node initializes embeddings with `init_embeddings(model=embed_model, **model_kwargs)`.
3. Node calls query embedding and gets dense vector.
4. Vector is passed to vector store search.
5. Results are filtered/ranked and returned.

### Flow 2: Chunk/document embedding for indexing

1. `ChunkEmbeddingNode` resolves chunk texts.
2. Node iterates separately over dense and sparse embedding spec maps:
   - `dense_embedding_specs` entries -> initialize via dense helper.
   - `sparse_embedding_specs` entries -> initialize via sparse helper.
3. Node embeds documents in batch and constructs vector records with explicit dense/sparse fields.
4. Records are persisted to vector store.

### Flow 3: Sparse retrieval + hybrid fusion

1. `SparseSearchNode` receives query text.
2. Node computes sparse query representation via sparse helper.
3. Sparse candidates are fetched from sparse-aware vector store.
4. Node applies lexical/BM25 scoring and returns sparse results.
5. `HybridFusionNode` fuses dense+sparse(+optional web) results.

### Flow 4: Evaluation semantic similarity

1. `SemanticSimilarityMetricsNode` resolves prediction/reference texts.
2. Node initializes embeddings via shared helper.
3. Node embeds texts and computes cosine similarity per pair.
4. Node returns per-item and corpus-level score.

## API Contracts

Node contract pattern after refactor:

```python
embed_model: str = Field(
    ...,
    description="Dense embedding model identifier, e.g. openai:text-embedding-3-small",
)
model_kwargs: dict[str, Any] = Field(
    default_factory=dict,
    description="Additional keyword arguments forwarded to init_embeddings.",
)
```

Sparse-capable node contract pattern:

```python
sparse_model: str = Field(
    ...,
    description="Sparse embedding model identifier, e.g. pinecone:bm25-default",
)
sparse_kwargs: dict[str, Any] = Field(
    default_factory=dict,
    description="Additional sparse-model kwargs passed to sparse initializer.",
)
```

`ChunkEmbeddingNode` embedding spec contract:

```python
dense_embedding_specs: dict[str, DenseEmbeddingSpec] = Field(
    default_factory=dict,
    description="Logical-name keyed dense embedding specs.",
)
sparse_embedding_specs: dict[str, SparseEmbeddingSpec] = Field(
    default_factory=dict,
    description="Logical-name keyed sparse embedding specs.",
)
```

Shared helper contract:

```python
def init_dense_embeddings(embed_model: str, model_kwargs: dict[str, Any]) -> Embeddings

async def embed_documents(
    model: Embeddings,
    texts: list[str],
) -> list[list[float]]

async def embed_query(
    model: Embeddings,
    text: str,
) -> list[float]
```

Sparse helper contract (shape):

```python
def init_sparse_embeddings(
    sparse_model: str,
    sparse_kwargs: dict[str, Any],
) -> SparseEmbedder

async def sparse_embed_documents(
    model: SparseEmbedder,
    texts: list[str],
) -> list[SparseValues]

async def sparse_embed_query(
    model: SparseEmbedder,
    text: str,
) -> SparseValues
```

Removed/changed contracts:
- Dense registry-centric resolution for core dense paths (`embedding_method`-style usage).
- Mixed generic embedding APIs where dense-only nodes currently accept sparse-only outputs.
- Legacy field names are not kept for compatibility in this milestone.

## Data Models / Schemas

Current key models impacted:

| Field | Current | New |
|-------|---------|-----|
| `embedding_method` (dense) | string key into global registry | replaced by `embed_model` |
| `embedding_methods` (mixed) | map of logical name -> registry key | replaced by separate `dense_embedding_specs` and `sparse_embedding_specs` maps |
| `provider` + `model` in some nodes | provider-specific embedding setup | replaced by `embed_model` |
| `model_kwargs` for embeddings | inconsistent or absent | standardized |
| sparse encoder configuration | hidden in registry methods | explicit `sparse_model` + `sparse_kwargs` in sparse-capable nodes |

Expected normalized embedding output from mixed producers:

```json
{
  "dense_embeddings": [[0.1, 0.2, 0.3]],
  "sparse_embeddings": [{"indices": [10, 42], "values": [0.7, 0.2]}]
}
```

Sparse payload shape is retained only for sparse-capable paths and vector-store adapters.

## Security Considerations

- Continue using existing credential template resolution (`[[...]]`) through decoded node fields.
- Avoid logging full `model_kwargs` when they contain secrets.
- Remove `credential_env_vars` from embedding node contracts.
- Pass provider credentials via `model_kwargs` so auth is handled through the unified embedding initialization kwargs.
- Ensure sparse kwargs handling does not leak encoder state paths or secret material.

## Performance Considerations

- Initial model construction may happen per node execution; consider lightweight caching keyed by `(embed_model, model_kwargs)` only if profiling shows overhead.
- Use batch embedding (`embed_documents`/`aembed_documents`) to preserve indexing throughput.
- For sparse encoders that require fitting/loading, cache initialized encoder instances when safe to avoid repeated fit/load costs.
- Preserve existing vector dimension mismatch checks in vector store adapters.

## Testing Strategy

- **Unit tests**:
  - dense embedding helper initialization and invocation paths
  - sparse embedding helper initialization and invocation paths
  - node-level behavior with new fields and error handling
  - invalid model/provider and malformed kwargs cases
- **Integration tests**:
  - conversational search ingestion + dense retrieval workflow still works
  - hybrid retrieval (dense+sparse fusion) still works
  - evaluation semantic similarity node produces expected scores
- **Manual QA checklist**:
  - run at least one indexing + retrieval example
  - run at least one hybrid indexing + hybrid retrieval example
  - verify existing initiative examples run with updated config keys
  - verify sparse references appear only in hybrid-specific examples

## Rollout Plan

1. Implement shared utility and update node schemas/runtime.
2. Implement explicit sparse helper and sparse-capable node contracts.
3. Update existing examples/configs in this initiative to new fields with dense/sparse lane separation.
4. Run lint + targeted tests + full relevant suite.
5. Merge as single breaking change.

No compatibility layer, feature flag, or temporary alias translator is planned for legacy dense field names or legacy dense model string prefixes (for example `embedding:openai:...`).

## Resolved Decisions

- `ChunkEmbeddingNode` embedding specs use separate dense and sparse maps (`dense_embedding_specs` and `sparse_embedding_specs`), not a discriminated union.
- No temporary alias translator will be implemented for legacy dense model strings like `embedding:openai:...`; configs/constants should be migrated directly to unified dense model identifiers.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-10 | Shaojie Jiang | Initial draft for dense model unification and explicit sparse-path contracts |
