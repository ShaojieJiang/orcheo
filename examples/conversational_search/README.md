# Conversational Search Demo Suite

Foundational assets for five progressive conversational search demos. Milestone 1 provides runnable scaffolds, shared sample data, and utilities so later milestones can focus on full workflows and guardrails.

## Quickstart
1. Copy `.env.example` to `.env` and add your API keys (OpenAI, Anthropic, Tavily).
2. Inspect `data/` to see the sample corpus, queries, and golden labels.
3. Run any demo script, for example:
   ```bash
   uv run python examples/conversational_search/demo_1_basic_rag/run.py
   ```

## What's Included
- Shared sample corpus (`data/docs`), baseline queries (`data/queries.json`), and golden labels (`data/golden`, `data/labels`).
- Five demo folders with config stubs, runner scripts, README scaffolds, and placeholder notebooks.
- `utils.py` with helpers for loading configs and datasets across demos.

## Demos
- **Demo 1: Basic RAG** – minimal ingestion and retrieval pipeline.
- **Demo 2: Hybrid Search** – dense + sparse retrieval with fusion.
- **Demo 3: Conversational Search** – stateful chat and query rewriting.
- **Demo 4: Production** – caching, guardrails, and streaming hooks.
- **Demo 5: Evaluation** – golden datasets, metrics, and feedback loops.

Each demo reads from the shared sample data by default. Replace the corpus or queries with your own domain content to experiment.
