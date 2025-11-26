# Demo 1: Basic RAG

Minimal retrieval-augmented generation pipeline using the shared sample corpus. This demo focuses on ingestion, chunking, indexing, and grounded generation with citations.

## Usage
This demo is designed to be uploaded and executed on the Orcheo server.

1. Upload `demo.py` to your Orcheo workspace.
2. The server will detect the `graph` entrypoint and `DEFAULT_CONFIG`.
3. Execute the workflow via the Orcheo Console or API.

## What to Expect
- Uses the shared markdown corpus in `../data/docs`.
- Loads baseline queries from `../data/queries.json`.
- Prints a summary of the dataset and the config sections wired for ingestion and retrieval.

## Next Steps
- Swap in your own markdown files under `data/docs`.
- Increase `top_k` or chunk sizes in `config.yaml` to explore retrieval changes.
