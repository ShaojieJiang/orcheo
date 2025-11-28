# Demo 1: Basic RAG Pipeline

A flexible conversational pipeline that supports both **RAG (Retrieval-Augmented Generation)** and **non-RAG** modes. This demo demonstrates document ingestion, chunking, indexing, vector search, and grounded generation with citations when documents are provided, or direct generation without retrieval when no documents are attached.

## Features

### RAG Mode (with documents)
- **Document Loading**: Load documents from disk using `DocumentLoaderNode`
- **Metadata Extraction**: Extract document metadata with `MetadataExtractorNode`
- **Chunking**: Split documents into chunks with configurable size and overlap using `ChunkingStrategyNode`
- **Embedding & Indexing**: Create embeddings and store in an in-memory vector store using `EmbeddingIndexerNode`
- **Vector Search**: Retrieve relevant chunks based on semantic similarity using `VectorSearchNode`
- **Grounded Generation**: Generate answers with citations using `GroundedGeneratorNode`

### Non-RAG Mode (without documents)
- **Direct Generation**: Generate responses without retrieval when no documents are provided
- **No Citations**: Responses are generated based on the model's knowledge without grounding in specific documents

## Usage

### Running Locally
```bash
python examples/conversational_search/demo_1_basic_rag/demo.py
```

This will demonstrate both modes:
1. **Non-RAG mode**: Answers a general knowledge question without any documents
2. **RAG mode**: Ingests a document and answers a question using the indexed content

### Uploading to Orcheo Server
1. Upload `demo.py` to your Orcheo workspace
2. The server will detect the `build_graph()` entrypoint and `DEFAULT_CONFIG`
3. Execute the workflow via the Orcheo Console or API with:
   - **For RAG mode**: Include `documents` in the input with `storage_path` to files
   - **For non-RAG mode**: Only include `message` without `documents`

## Configuration

The demo uses `DEFAULT_CONFIG` for customization:

```python
DEFAULT_CONFIG = {
    "ingestion": {
        "chunking": {
            "chunk_size": 512,      # Size of each text chunk
            "chunk_overlap": 64,    # Overlap between chunks
        },
    },
    "retrieval": {
        "search": {
            "top_k": 5,                    # Number of chunks to retrieve
            "similarity_threshold": 0.0,   # Minimum similarity score
        },
    },
}
```

## Workflow Architecture

The workflow uses conditional routing to support both modes:

```
START
  ├─ Documents provided?
  │    ├─ YES → DocumentLoader → Metadata → Chunking → Indexer
  │    │                                                  ↓
  │    │                                         Query exists?
  │    │                                           ├─ YES → VectorSearch → Generator
  │    │                                           └─ NO → END
  │    └─ NO → Has indexed documents?
  │              ├─ YES → VectorSearch → Generator (RAG mode)
  │              └─ NO → Generator (Non-RAG mode)
  └─ END
```

## Example Inputs

### RAG Mode
```python
{
    "inputs": {
        "documents": [
            {
                "storage_path": "/path/to/document.txt",
                "source": "document.txt",
                "metadata": {"category": "tech"}
            }
        ],
        "message": "What is Orcheo?"
    }
}
```

### Non-RAG Mode
```python
{
    "inputs": {
        "message": "What is the capital of France?"
    }
}
```

## Expected Outputs

### RAG Mode Output
```python
{
    "reply": "Orcheo is a powerful workflow orchestration platform... [1]",
    "citations": [
        {
            "id": "1",
            "source_id": "...",
            "snippet": "Orcheo is a powerful workflow orchestration platform...",
            "sources": ["document.txt"]
        }
    ],
    "tokens_used": 156,
    "citation_style": "inline",
    "mode": "rag"
}
```

### Non-RAG Mode Output
```python
{
    "reply": "The capital of France is Paris...",
    "citations": [],
    "tokens_used": 42,
    "citation_style": "inline",
    "mode": "non_rag"
}
```

## Next Steps

- **Customize chunking**: Adjust `chunk_size` and `chunk_overlap` for different document types
- **Tune retrieval**: Modify `top_k` and `similarity_threshold` to balance precision/recall
- **Add real LLM**: Replace the default mock LLM with OpenAI, Anthropic, or other providers
- **Try different documents**: Upload your own markdown files to test domain-specific RAG
- **Experiment with modes**: Test the workflow with and without documents to see both behaviors
