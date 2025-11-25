# Demo 1: Basic RAG

Minimal retrieval-augmented generation pipeline using the shared sample corpus. This demo focuses on ingestion, chunking, indexing, and grounded generation with citations.

## Run Locally
1. Ensure `.env` is populated with your API keys (see `.env.example` in the parent folder).
2. Execute the runner:
   ```bash
   uv run python examples/conversational_search/demo_1_basic_rag/run.py
   ```

## What to Expect
- Uses the shared markdown corpus in `../data/docs`.
- Loads baseline queries from `../data/queries.json`.
- Prints a summary of the dataset and the config sections wired for ingestion and retrieval.

## Next Steps
- Swap in your own markdown files under `data/docs`.
- Increase `top_k` or chunk sizes in `config.yaml` to explore retrieval changes.
