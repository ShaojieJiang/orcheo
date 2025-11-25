# Demo 4: Production-Ready Pipeline

Production-focused scaffold with caching, guardrails, streaming, and incremental indexing hooks. The config is tuned for local experimentation against the shared sample corpus.

## Run Locally
```bash
uv run python examples/conversational_search/demo_4_production/run.py
```

## Notes
- Shows how to toggle caching, hallucination guards, and policy checks.
- Includes session controls and streaming defaults for fast iteration.
- Prints dataset summary plus the key production toggles defined in `config.yaml`.
