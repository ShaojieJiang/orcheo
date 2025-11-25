# Conversational Search Demo Data

This folder contains the shared sample corpus, queries, and labels used by the conversational search demo suite. The data is intentionally small so the demos can run locally without external dependencies.

## Contents
- `docs/`: Markdown knowledge base about the fictitious Orcheo Cloud product.
- `queries.json`: Baseline user questions with intents and expected focus areas.
- `golden/`: Golden queries and expected answers for evaluation-heavy demos.
- `labels/relevance_labels.json`: Sparse relevance labels for retrieval metrics.

## Usage
- Demos point to these files by default in their `config.yaml`. You can replace the corpus or add more examples without changing the runner code.
- Keep additions small and text-based so linting and tests stay fast.
