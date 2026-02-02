# Design Document

## For MongoDB node modularization and hybrid search nodes

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2026-02-02
- **Status:** Approved

---

## Overview

This design modularizes the MongoDB node implementation into a package under a shared integrations tree and adds purpose-built nodes for Atlas Search index management and hybrid search. The intent is to keep the generic `MongoDBNode` intact for advanced use cases while providing higher-level nodes that encapsulate common patterns: idempotent index creation and rank-fusion hybrid search. These nodes should minimize boilerplate, standardize index naming, and improve developer ergonomics.
Default index names are `orcheo_{collection}_fts` for full-text and `orcheo_{collection}_vec` for vector unless explicitly overridden. Hybrid search uses reciprocal rank fusion by default.

## Components

- **MongoDB base nodes (`src/orcheo/nodes/integrations/databases/mongodb/base.py`)**
  - Retains `MongoDBNode`, `MongoDBFindNode`, `MongoDBAggregateNode`, and `MongoDBUpdateManyNode`.
  - Keeps shared client/session management and generic operation execution.

- **MongoDB search nodes (`src/orcheo/nodes/integrations/databases/mongodb/search.py`)**
  - `MongoDBEnsureSearchIndexNode` for full-text index management.
  - `MongoDBEnsureVectorIndexNode` for vector index management.
  - `MongoDBHybridSearchNode` for hybrid search pipeline construction and execution.

- **Package exports (`src/orcheo/nodes/integrations/databases/mongodb/__init__.py`)**
  - Re-exports base and search nodes for internal use; compatibility exports live in `src/orcheo/nodes/mongodb.py` and `src/orcheo/nodes/__init__.py`.

- **Examples (`examples/mongodb.py`)**
  - Demonstrates index creation and hybrid search in a small workflow.

## Request Flows

### Flow 1: Ensure full-text search index
1. Node connects to MongoDB collection.
2. Calls `list_search_indexes` to fetch existing indexes.
3. If index name missing, calls `create_search_index`.
4. If index exists and mode is `ensure_or_update`, normalize and deep-compare definitions, then call `update_search_index` on any mismatch.
5. Returns result payload (created/updated/skipped).

### Flow 2: Ensure vector search index
1. Node connects and lists search indexes.
2. If missing, creates index with vector mappings (dimensions, similarity).
3. If mode is `ensure_or_update`, normalize and deep-compare definitions, then update on any mismatch.
4. Returns result payload.

### Flow 3: Hybrid search
1. Node validates inputs (`text_query` or `vector` required).
2. Builds a reciprocal-rank-fusion pipeline that combines `$search` and `$vectorSearch` subpipelines.
3. Executes `aggregate` against the collection.
4. Normalizes results into a standard wrapper (id, score, raw).

## API Contracts

### MongoDBEnsureSearchIndexNode
Inputs (pydantic fields):
- `connection_string`, `database`, `collection`
- `index_name` (optional, defaults to `orcheo_{collection}_fts`)
- `definition` (dict)
- `mode`: `ensure` | `ensure_or_update` | `force_rebuild`

Outputs:
- `{ "status": "created" | "updated" | "skipped", "index_name": str }`

### MongoDBEnsureVectorIndexNode
Inputs:
- `connection_string`, `database`, `collection`
- `index_name` (optional, defaults to `orcheo_{collection}_vec`)
- `definition`
- `dimensions`, `similarity`, `path` (optional convenience inputs used to build definition)
- `mode`

Outputs:
- `{ "status": "created" | "updated" | "skipped", "index_name": str }`

### MongoDBHybridSearchNode
Inputs:
- `connection_string`, `database`, `collection`
- `text_query` (str | None)
- `vector` (list[float] | None)
- `text_paths` (list[str])
- `vector_path` (str)
- `text_index_name` (optional, defaults to `orcheo_{collection}_fts`)
- `vector_index_name` (optional, defaults to `orcheo_{collection}_vec`)
- `top_k`, `num_candidates`
- `rrf_k` (optional reciprocal-rank-fusion constant)
- `filter` (optional)

Outputs:
- `{ "results": [{"id": str, "score": float, "raw": dict}] }`

## Data Models / Schemas

### Example full-text index definition
```json
{
  "name": "orcheo_{collection}_fts",
  "definition": {
    "mappings": {
      "dynamic": false,
      "fields": {
        "title": {"type": "string"},
        "body": {"type": "string"}
      }
    }
  }
}
```

### Example vector index definition
```json
{
  "name": "orcheo_{collection}_vec",
  "definition": {
    "mappings": {
      "dynamic": false,
      "fields": {
        "embedding": {
          "type": "vector",
          "dimensions": 1536,
          "similarity": "cosine"
        }
      }
    }
  }
}
```

## Security Considerations

- Require credentials via `connection_string`; avoid logging secrets.
- Index operations require Atlas Search privileges; surface authorization errors clearly.
- Validate inputs to avoid arbitrary pipeline injection in the high-level hybrid node.

## Performance Considerations

- Listing indexes adds a small overhead; acceptable for one-time setup.
- Index creation is expensive; default behavior should be idempotent and skip when present.
- Hybrid search should allow tuning `num_candidates` and `top_k`.

## Testing Strategy

- **Unit tests**: normalized index diffing, mode handling (create/update/skip), pipeline builder.
- **Integration tests**: mock `MongoClient` and `Collection` methods; verify method calls.
- **Example validation**: ensure `examples/mongodb.py` runs with minimal setup.

## Rollout Plan

1. Add new module directory and search nodes.
2. Update imports and examples.
3. Add tests and run lint/test checks.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-02 | Codex | Update paths to integrations tree and compatibility exports |
| 2026-02-02 | Codex | Initial draft |
