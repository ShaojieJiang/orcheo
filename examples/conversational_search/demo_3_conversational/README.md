# Demo 3: Conversational Search

Stateful, multi-turn chat that wires conversation memory, query routing, coreference
resolution, and topic-shift detection into a single flow.

## What this workflow demonstrates
- **ConversationStateNode** keeps the session history and summary in an in-memory
  store while capping the turn count.
- **QueryClassifierNode** routes traffic between search, clarification, and
  finalize branches.
- **CoreferenceResolverNode / QueryRewriteNode** rewrite pronouns using the
  most recent context so retrieval keeps pace with the user.
- **DenseSearchNode + GroundedGeneratorNode** answer questions with grounded
  responses retrieved from the Pinecone index that Demo 0 populated.
- **TopicShiftDetectorNode** flags divergence from the prior subject.
- **QueryClarificationNode** emits clarifying questions when the classifier
  picks the `clarification` branch.
- **MemorySummarizerNode** persists a compact summary when the user signals
  finalization.

## Default configuration
```python
DEFAULT_CONFIG = {
    "conversation": {"max_turns": 20, "max_sessions": 8, "max_total_turns": 160},
    "query_processing": {"topic_shift": {"similarity_threshold": 0.4, "recent_turns": 3}},
    "retrieval": {"top_k": 3, "score_threshold": 0.0},
    "generation": {"citation_style": "inline"},
    "vector_store": {
        "type": "pinecone",
        "index_name": "orcheo-demo-dense",
        "namespace": "hybrid_search",
        "client_kwargs": {
            "api_key": "[[pinecone_api_key]]",
        },
    },
}
```

## Running locally
1. Run Demo 0 (`examples/conversational_search/demo_0_hybrid_indexing/demo_0.py`)
   to populate the Pinecone indexes from `examples/conversational_search/data/docs`
   (authentication, product overview, troubleshooting).
2. Ensure the Pinecone credentials (`pinecone_api_key`) are available to the demo
   via the Orcheo vault.
3. Run `python examples/conversational_search/demo_3_conversational/demo_3.py`.
4. The script prints the conversation controls from `DEFAULT_CONFIG`, confirms
   the Pinecone index it will query, and then steps through five scripted turns:
   - Query classification and coreference resolution for follow-ups
   - Clarification prompts when ambiguity is detected
   - Topic-shift detection pointing out a move to troubleshooting
   - Memory summarization when the user indicates a final question

The workflow is also designed for Orcheo: `build_graph` is the entrypoint the
server uses to compile the graph when uploading this demo.
