# Demo 3: Conversational Search

Stateful multi-turn chat with query classification, rewriting, and topic-shift detection. This scaffold wires the sample corpus to a conversational pipeline without external dependencies.

## Usage
This demo is designed to be uploaded and executed on the Orcheo server.

1. Upload `demo.py` to your Orcheo workspace.
2. The server will detect the `graph` entrypoint and `DEFAULT_CONFIG`.
3. Execute the workflow via the Orcheo Console or API.

## What to Expect
- Demonstrates classifier, coreference resolver, and query rewriter configs.
- Uses in-memory conversation state with a 20-turn limit for the preview.
- Prints the loaded dataset summary and the conversation controls from `DEFAULT_CONFIG`.
