# Conversational Search Demo Suite

Foundational assets for five progressive conversational search demos. Milestone 1 provides runnable scaffolds, shared sample data, and utilities so later milestones can focus on full workflows and guardrails.

## Quickstart (< 5 minutes)

### Step 0: Check Your Setup (Optional but Recommended)
Run the setup checker to verify all prerequisites:

```bash
python examples/conversational_search/check_setup.py
```

This will check your Python version, dependencies, credentials, and data files, then provide guidance on any missing items.

### Prerequisites
1. **Install dependencies**:
   ```bash
   uv sync --group examples
   ```
   This installs the `examples` dependency group including `orcheo-backend` for credential vault access.

2. **Set up credentials** (for OpenAI-based demos):
   ```bash
   orcheo credential create openai_api_key --secret sk-your-key-here
   ```
   The demos use the Orcheo vault (`~/.orcheo/vault.sqlite`) for secure credential storage.

### Run Demo 2 (Recommended First Demo)
Demo 2 works entirely locally with no external vector database required:

```bash
python examples/conversational_search/demo_2_basic_rag/demo_2.py
```

**What to expect:**
- The demo runs in two phases: non-RAG (direct generation) and RAG (with document ingestion)
- Takes ~1-2 minutes to complete both phases
- Output shows routing decisions, retrieval results, and generated responses with citations

### Other Demos
- **Demo 3, 4, 5, 6** require Pinecone credentials and indexed data
- See individual demo READMEs for specific requirements
- Most demos are designed for deployment to Orcheo server

### Quick Credential Reference
- **Demo 1**: `openai_api_key`, `pinecone_api_key`
- **Demo 2**: `openai_api_key`
- **Demo 3**: `openai_api_key`, `tavily_api_key`
- **Demo 4, 5, 6**: `openai_api_key`, `pinecone_api_key`

Create credentials with: `orcheo credential create <name> --secret <value>`

## Dependency groups

- `uv sync --all-groups` brings in the core project, docs, and tooling dependencies needed to work with these demos.
- `uv sync --group examples` installs the new `examples` dependency group (which adds the `orcheo-backend` workspace package) so scripts that rely on `orcheo_backend.app.dependencies` can resolve the vault helpers.

## What's Included
- Shared sample corpus (`data/docs`), baseline queries (`data/queries.json`), and golden labels (`data/golden`, `data/labels`).
- Five demo folders with config stubs, runner scripts, README scaffolds, and placeholder notebooks.
- `utils.py` with helpers for loading configs and datasets across demos.

## Demos
- **Demo 1: Hybrid Indexing** – index corpus into Pinecone for hybrid search.
- **Demo 2: Basic RAG** – minimal ingestion and retrieval pipeline.
- **Demo 3: Hybrid Search** – dense + sparse retrieval with fusion.
- **Demo 4: Conversational Search** – stateful chat and query rewriting.
- **Demo 5: Production** – caching, guardrails, and streaming hooks.
- **Demo 6: Evaluation** – golden datasets, metrics, and feedback loops.

Each demo reads from the shared sample data by default. Replace the corpus or queries with your own domain content to experiment.
