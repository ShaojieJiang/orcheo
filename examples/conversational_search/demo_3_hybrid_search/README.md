# Demo 3: Hybrid Search (1 indexing + 3 retrieval)

Dense + sparse retrieval with reciprocal-rank fusion, optional web search, and an AI context summarizer. Demo 1 indexes the local corpus into Pinecone; Demo 3 assumes those indexes exist and runs the retrieval + fusion workflow.

## Usage
These demos are designed to be uploaded and executed on the Orcheo server.

1) **Index**: upload and run `examples/conversational_search/demo_1_hybrid_indexing/demo_1.py` to upsert deterministic embeddings + metadata into Pinecone.
2) **Query**: upload and run `examples/conversational_search/demo_3_hybrid_search/demo_3.py` to fan queries across dense, sparse, and web search before fusion and ranking.

## What to Expect
- `examples/conversational_search/demo_1_hybrid_indexing/demo_1.py` prints the corpus stats and the Pinecone namespace/index used.
- `examples/conversational_search/demo_3_hybrid_search/demo_3.py` uses `bm25`, `vector`, and `web_search` branches defined in `DEFAULT_CONFIG` and outputs a grounded answer with citations.
- Modify `DEFAULT_CONFIG` directly in each script to tune how each retriever contributes.
