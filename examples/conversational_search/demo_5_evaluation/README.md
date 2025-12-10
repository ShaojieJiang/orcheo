# Demo 5: Evaluation & Research

Evaluation-focused scaffold with golden datasets, relevance labels, and variant definitions for retrieval A/B tests. This workflow assumes you have already run **Demo 0 (Hybrid Search Indexing)** so the Pinecone indexes are populated; it no longer builds an in-memory vector store.

## Usage
This demo is designed to be uploaded and executed on the Orcheo server.

1. Upload `demo.py` to your Orcheo workspace.
2. The server will detect the `graph` entrypoint and `DEFAULT_CONFIG`.
3. Execute the workflow via the Orcheo Console or API.

## What to Expect
- Golden queries live in `../data/golden/golden_dataset.json` with paired relevance labels in `../data/labels/relevance_labels.json`.
- Config includes variant definitions for comparing retrieval strategies.
- Runner prints dataset and variant summaries to validate the setup before wiring full evaluators.
