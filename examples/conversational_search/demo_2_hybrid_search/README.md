# Demo 2: Hybrid Search

Dense + sparse retrieval with reciprocal-rank fusion, optional web search, and a re-ranker. Uses the shared corpus and sample queries to illustrate how fusion changes context assembly.

## Usage
This demo is designed to be uploaded and executed on the Orcheo server.

1. Upload `demo.py` to your Orcheo workspace.
2. The server will detect the `graph` entrypoint and `DEFAULT_CONFIG`.
3. Execute the workflow via the Orcheo Console or API.

## What to Expect
- Uses `bm25`, `vector`, and `web_search` branches defined in `DEFAULT_CONFIG`.
- Prints a preview of the configured retrieval stack and the sample dataset.
- Modify `DEFAULT_CONFIG` in demo.py to tune how each retriever contributes.
