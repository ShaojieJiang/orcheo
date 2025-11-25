# Demo 2: Hybrid Search

Dense + sparse retrieval with reciprocal-rank fusion, optional web search, and a re-ranker. Uses the shared corpus and sample queries to illustrate how fusion changes context assembly.

## Run Locally
```bash
uv run python examples/conversational_search/demo_2_hybrid_search/run.py
```

## Notes
- Uses `bm25`, `vector`, and `web_search` branches defined in `config.yaml`.
- Prints a preview of the configured retrieval stack and the sample dataset.
- Extend `fusion.weights` to tune how each retriever contributes.
