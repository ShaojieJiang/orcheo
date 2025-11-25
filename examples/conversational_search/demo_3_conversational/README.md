# Demo 3: Conversational Search

Stateful multi-turn chat with query classification, rewriting, and topic-shift detection. This scaffold wires the sample corpus to a conversational pipeline without external dependencies.

## Run Locally
```bash
uv run python examples/conversational_search/demo_3_conversational/run.py
```

## Notes
- Demonstrates classifier, coreference resolver, and query rewriter configs.
- Uses in-memory conversation state with a 20-turn limit for the preview.
- Prints the loaded dataset summary and the conversation controls from `config.yaml`.
