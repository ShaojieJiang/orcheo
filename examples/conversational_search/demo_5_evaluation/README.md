# Demo 5: Evaluation & Research

Evaluation-focused scaffold with golden datasets, relevance labels, and variant definitions for retrieval A/B tests. Use this as the starting point for metrics, analytics, and feedback loops.

## Run Locally
```bash
uv run python examples/conversational_search/demo_5_evaluation/run.py
```

## Notes
- Golden queries live in `../data/golden/golden_dataset.json` with paired relevance labels in `../data/labels/relevance_labels.json`.
- Config includes variant definitions for comparing retrieval strategies.
- Runner prints dataset and variant summaries to validate the setup before wiring full evaluators.
