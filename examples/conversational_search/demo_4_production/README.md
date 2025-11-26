# Demo 4: Production-Ready Pipeline

Production-focused scaffold with caching, guardrails, streaming, and incremental indexing hooks. The config is tuned for server-side execution against the shared sample corpus.

## Usage
This demo is designed to be uploaded and executed on the Orcheo server.

1. Upload `demo.py` to your Orcheo workspace.
2. The server will detect the `graph` entrypoint and `DEFAULT_CONFIG`.
3. Execute the workflow via the Orcheo Console or API.

## What to Expect
- Shows how to toggle caching, hallucination guards, and policy checks.
- Includes session controls and streaming defaults for fast iteration.
- Prints dataset summary plus the key production toggles defined in `DEFAULT_CONFIG`.
