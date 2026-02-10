# Conversational Search Evaluation

Evaluation workflows for QReCC (query rewriting) and MultiDoc2Dial (grounded generation) benchmarks, built as native Orcheo workflows.

**Author:** ShaojieJiang

## Overview

This directory contains evaluation pipelines for two complementary conversational search benchmarks:

| Dataset | Task | Split | Metrics |
|---------|------|-------|---------|
| **QReCC** | Query rewriting | test (2,775 conversations, 16,451 turns) | ROUGE-1 Recall, Semantic Similarity |
| **MultiDoc2Dial** | Grounded generation | validation (661 dialogues, 4,201 queries) | Token F1, SacreBLEU, ROUGE-L |

## Directory Structure

```
examples/evaluation/
├── README.md                       # This file
├── __init__.py
├── qrecc_eval.py                   # QReCC evaluation workflow
├── md2d_eval.py                    # MultiDoc2Dial evaluation workflow
├── md2d_indexing.py                # MultiDoc2Dial corpus indexing workflow
├── run_all.py                      # Unified runner for both evaluations
├── config_qrecc.json               # QReCC evaluation config
├── config_md2d.json                # MultiDoc2Dial evaluation config
├── config_md2d_indexing.json       # MultiDoc2Dial corpus indexing config
└── data/                           # Data directory (download separately)
    ├── qrecc_test.json
    ├── md2d_validation.json
    └── md2d_docs/
```

## Data Download

### QReCC

Download the QReCC dataset from [Hugging Face](https://huggingface.co/datasets/apple/QReCC):

```bash
mkdir -p examples/evaluation/data
# Download QReCC test split
python -c "
from datasets import load_dataset
import json
ds = load_dataset('apple/QReCC', split='test')
with open('examples/evaluation/data/qrecc_test.json', 'w') as f:
    json.dump([dict(row) for row in ds], f)
"
```

### MultiDoc2Dial

Download the MultiDoc2Dial dataset from [Hugging Face](https://huggingface.co/datasets/doc2dial/MultiDoc2Dial):

```bash
# Download MultiDoc2Dial validation split
python -c "
from datasets import load_dataset
import json
ds = load_dataset('doc2dial/MultiDoc2Dial', split='validation')
with open('examples/evaluation/data/md2d_validation.json', 'w') as f:
    json.dump([dict(row) for row in ds], f)
"
```

## Setup

Install Orcheo with evaluation dependencies:

```bash
pip install orcheo
# or with uv
uv pip install orcheo
```

Required packages (included in Orcheo dependencies):
- `rouge-score>=0.1.2` — ROUGE metric computation
- `sacrebleu>=2.3.0` — SacreBLEU metric computation
- `langchain-openai` — Semantic similarity embeddings (optional)

Create required vault credential before running model-backed workflows:

```bash
orcheo credential create openai_api_key --secret sk-your-key-here
```

## Running Evaluations

### QReCC Evaluation

```bash
orcheo workflow upload examples/evaluation/qrecc_eval.py \
    --config-file examples/evaluation/config_qrecc.json
orcheo workflow run <workflow-id>
```

### MultiDoc2Dial Evaluation

**Step 1: Index the corpus** (required once):
```bash
orcheo workflow upload examples/evaluation/md2d_indexing.py \
    --config-file examples/evaluation/config_md2d_indexing.json
orcheo workflow run <workflow-id>
```

**Step 2: Run evaluation**
```bash
orcheo workflow upload examples/evaluation/md2d_eval.py \
    --config-file examples/evaluation/config_md2d.json
orcheo workflow run <workflow-id>
```

### Unified Runner

Run both evaluations:
```bash
python examples/evaluation/run_all.py
```

### Quick Iteration

Limit conversations for faster feedback during development:

```bash
# Edit config to set max_conversations
# e.g., in config_qrecc.json:
# "max_conversations": 10
```

## Interpreting Results

### QReCC Metrics

| Metric | Description | Range |
|--------|-------------|-------|
| **ROUGE-1 Recall** | Unigram overlap between predicted and gold rewrite | 0.0–1.0 |
| **Semantic Similarity** | Embedding cosine similarity (requires API key) | 0.0–1.0 |

Higher is better. A score of 1.0 on identical rewrites confirms correct pipeline wiring.

### MultiDoc2Dial Metrics

| Metric | Description | Range |
|--------|-------------|-------|
| **Token F1** | Token-level precision/recall/F1 between prediction and gold | 0.0–1.0 |
| **SacreBLEU** | Corpus-level BLEU score | 0.0–100.0 |
| **ROUGE-L** | Longest common subsequence overlap (F-measure) | 0.0–1.0 |

### Report Output

Each evaluation produces a JSON report and formatted table:

```
Metric                              Score
----------------------------------------
rouge1_recall                       0.7800
semantic_similarity                 0.8500
```

## Configuration

Each dataset has a single config file that controls data paths, model selections, and evaluation limits:

| Config | Key Parameters |
|--------|----------------|
| `config_qrecc.json` | `data_path`, `max_conversations`, similarity `model` and `dimensions` |
| `config_md2d.json` | `data_path`, `max_conversations`, retrieval `embedding_method` and `top_k`, generation `model` |
| `config_md2d_indexing.json` | `docs_path`, `chunk_size`, `chunk_overlap`, `embedding_method` |

Users can create custom configs with different model or retrieval parameters to compare pipeline configurations against the established baselines.

## Architecture

All evaluation pipelines are native Orcheo workflows using registered nodes:

```
QReCCDatasetNode → ConversationalBatchEvalNode → RougeMetricsNode → MetricReportWriterNode
                                                → SemanticSimilarityMetricsNode ↗

MultiDoc2DialDatasetNode → ConversationalBatchEvalNode → TokenF1MetricsNode → MetricReportWriterNode
                                                        → BleuMetricsNode ↗
                                                        → RougeMetricsNode ↗
```

Metric nodes follow a uniform output contract:
```python
{"metric_name": str, "corpus_score": float, "per_item": list[float]}
```

## Node Reference

| Node | Module | Description |
|------|--------|-------------|
| `QReCCDatasetNode` | `evaluation/datasets.py` | Load QReCC conversations with gold rewrites |
| `MultiDoc2DialDatasetNode` | `evaluation/datasets.py` | Load MultiDoc2Dial conversations with grounding spans |
| `ConversationalBatchEvalNode` | `evaluation/batch.py` | Iterate conversations/turns, collect predictions and references |
| `RougeMetricsNode` | `evaluation/metrics.py` | Configurable ROUGE scoring |
| `BleuMetricsNode` | `evaluation/metrics.py` | SacreBLEU scoring |
| `SemanticSimilarityMetricsNode` | `evaluation/metrics.py` | Embedding cosine similarity |
| `TokenF1MetricsNode` | `evaluation/metrics.py` | Token-level F1 scoring |
| `MetricReportWriterNode` | `evaluation/metrics.py` | Format metrics into reports and tables |
