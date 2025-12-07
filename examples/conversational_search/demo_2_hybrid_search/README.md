# Demo 2: Hybrid Search (2.1 indexing + 2.2 retrieval)

Dense + sparse retrieval with reciprocal-rank fusion, optional web search, and an AI context summarizer. Demo 2.1 indexes the local corpus into Pinecone; Demo 2.2 assumes those indexes exist and runs the retrieval + fusion workflow.

## Usage
These demos are designed to be uploaded and executed on the Orcheo server.

1) **Index**: upload and run `examples/conversational_search/demo_0_hybrid_indexing/demo_0.py` to upsert deterministic embeddings + metadata into Pinecone.
2) **Query**: upload and run `examples/conversational_search/demo_2_hybrid_search/demo_2.py` to fan queries across dense, sparse, and web search before fusion and ranking.

## What to Expect
- `examples/conversational_search/demo_0_hybrid_indexing/demo_0.py` prints the corpus stats and the Pinecone namespace/index used.
- `examples/conversational_search/demo_2_hybrid_search/demo_2.py` uses `bm25`, `vector`, and `web_search` branches defined in `DEFAULT_CONFIG` and outputs a grounded answer with citations.
- Modify `DEFAULT_CONFIG` directly in each script to tune how each retriever contributes.
