# Evaluation

This guide covers the benchmark evaluation workflows in `examples/evaluation/`.

## Overview

The evaluation examples provide two benchmark tracks:

- **QReCC rewrite evaluation** (`examples/evaluation/qrecc_eval.py`)
- **MultiDoc2Dial grounded generation evaluation** (`examples/evaluation/md2d_eval.py`)

A separate indexing workflow is included for MultiDoc2Dial corpus ingestion:

- **MultiDoc2Dial corpus indexing** (`examples/evaluation/md2d_indexing.py`)

## Prerequisites

1. Install dependencies:

```bash
uv sync --all-groups
```

2. Create required credentials:

```bash
orcheo credential create openai_api_key --secret sk-your-key-here
orcheo credential create pinecone_api_key --secret your-pinecone-key
```

## Data Sources

Default configs use hosted benchmark artifacts:

- QReCC test set via Hugging Face (`config_qrecc.json`)
- MultiDoc2Dial validation dialogs and corpus (`config_md2d.json`, `config_md2d_indexing.json`)

## Workflow: QReCC

Upload and run:

```bash
orcheo workflow upload examples/evaluation/qrecc_eval.py \
  --config-file examples/evaluation/config_qrecc.json
orcheo workflow run <workflow-id> --verbose
```

Pipeline summary:

1. `QReCCDatasetNode` loads and structures conversations.
2. `ConversationalBatchEvalNode` executes per-turn rewrite evaluation.
3. `RougeMetricsNode` + `SemanticSimilarityMetricsNode` score outputs.
4. `AnalyticsExportNode` merges corpus metrics and per-conversation views.

## Workflow: MultiDoc2Dial

### Step 1: Index corpus (run once per index/namespace)

```bash
orcheo workflow upload examples/evaluation/md2d_indexing.py \
  --config-file examples/evaluation/config_md2d_indexing.json
orcheo workflow run <workflow-id>
```

### Step 2: Run evaluation

```bash
orcheo workflow upload examples/evaluation/md2d_eval.py \
  --config-file examples/evaluation/config_md2d.json
orcheo workflow run <workflow-id> --verbose
```

Pipeline summary:

1. `MultiDoc2DialDatasetNode` loads/normalizes conversations.
2. `ConversationalBatchEvalNode` runs rewrite -> retrieval -> generation per turn.
3. `TokenF1MetricsNode`, `BleuMetricsNode`, and `RougeMetricsNode` score outputs.
4. `AnalyticsExportNode` aggregates metric outputs into a report payload.

## Config Notes

Key config values you will typically tune:

- `max_conversations` / `max_documents` for faster iteration loops.
- `retrieval.embed_model` and `retrieval.dimensions` for embedding behavior.
- `vector_store.pinecone.index_name` and `namespace` for isolation.
- `generation.model` and rewrite model settings.

## Expected Outputs

`AnalyticsExportNode` returns:

- `report.metrics`: corpus-level metric map
- `report.per_conversation`: per-conversation aggregated scores
- `table`: markdown-style metric table
- `report_json`: pretty-printed JSON payload

## Related Docs

- [Conversational Search](conversational_search.md)
- [CLI Reference](../cli_reference.md)
- [SDK Reference](../sdk_reference.md)
