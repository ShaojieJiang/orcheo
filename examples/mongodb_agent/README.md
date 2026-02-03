# MongoDB Agent Workflows

Three workflows that scrape web content into MongoDB, set up Atlas Search
indexes, and expose a ChatKit-ready QA agent.

## Prerequisites
- MongoDB Atlas cluster with Search enabled and a collection you can write to.
- Orcheo vault credentials `mdb_connection_string` and `openai_api_key`.
- Dependencies installed via `uv sync --group examples`.

Create credentials:

```bash
orcheo credential create mdb_connection_string --secret "mongodb+srv://..."
orcheo credential create openai_api_key --secret "sk-..."
```

## Configuration
Edit `config.json`:
- `database`, `collection`: target MongoDB location.
- `vector_path`: field name to store vectors (must match index path).
- `text_paths`: fields searched by Atlas Search.
- `embedding_method`: embedding registry key.
- `dimensions`: must match the embedding output dimension.
- `urls`: list of pages to scrape for ingestion.
- `ai_model`, `system_prompt`: agent behavior.

## Run the Workflows
1. Web scrape + upload:

   ```bash
   orcheo workflow upload examples/mongodb_agent/01_web_scrape_and_upload.py \
     --config-file examples/mongodb_agent/config.json \
     --name "MongoDB: Scrape + Upload"
   orcheo workflow run <workflow-id>
   ```

   This inserts documents with `body` text, metadata, and the `vector_path`
   embedding.

2. Create search + vector indexes:

   ```bash
   orcheo workflow upload examples/mongodb_agent/02_create_index_and_hybrid_search.py \
     --config-file examples/mongodb_agent/config.json \
     --name "MongoDB: Ensure Indexes"
   orcheo workflow run <workflow-id>
   ```

   This ensures Atlas Search and vector indexes exist; hybrid search is used
   by the agent workflow in step 3.

3. QA agent (ChatKit-ready):

   ```bash
   orcheo workflow upload examples/mongodb_agent/03_qa_agent.py \
     --config-file examples/mongodb_agent/config.json \
     --name "MongoDB: QA Agent"
   orcheo workflow run <workflow-id> --inputs '{"message": "What was announced?"}'
   ```

   For the ChatKit UI, publish the workflow and follow
   `docs/chatkit_integration/workflow_publish_guide.md`.
