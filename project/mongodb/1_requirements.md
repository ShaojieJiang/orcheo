# Requirements Document Template

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** MongoDB nodes modularization + hybrid search nodes
- **Type:** Enhancement
- **Summary:** Move MongoDB node implementation into a future-proof integrations tree and add purpose-built nodes for index management and hybrid search, with an updated example.
- **Owner (if different than authors):** ShaojieJiang
- **Date Started:** 2026-02-02

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Prior Artifacts | src/orcheo/nodes/mongodb.py | Eng | MongoDBNode implementation |
| Prior Artifacts | examples/mongodb.py | Eng | MongoDB example |
| Design Review | project/mongodb/2_design.md | Eng | MongoDB nodes design |
| Plan | project/mongodb/3_plan.md | Eng | MongoDB nodes plan |

## PROBLEM DEFINITION
### Objectives
Reduce MongoDB workflow boilerplate by introducing dedicated nodes for index management and hybrid search, while keeping the base MongoDB node intact. Improve maintainability by moving MongoDB node code into a module directory under a shared integrations tree so related external systems can be grouped consistently.

### Target users
Orcheo developers building MongoDB Atlas search workflows (full-text, vector, or hybrid search).

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Workflow author | Create a full-text search index if missing | I can prepare search without manual admin scripts | P0 | Node checks indexes and creates one when absent |
| Workflow author | Create a vector search index if missing | I can use embeddings without writing raw index definitions each time | P0 | Node checks/creates vector index with dimensions + similarity |
| Workflow author | Run hybrid search with a single node | I avoid hand-building rank-fusion pipelines | P0 | Node accepts text + vector inputs and returns ranked results |
| Maintainer | Keep MongoDB nodes maintainable | I can add features without a single mega-file | P1 | MongoDB code becomes a module directory with separated files |

### Context, Problems, Opportunities
The current MongoDB node supports raw aggregation pipelines and search index operations but requires manual construction of index definitions and rank-fusion pipelines. This leads to repeated boilerplate in examples and workflows, and the existing file is already large, making it harder to extend. Purpose-built nodes can improve developer experience while preserving the generic node for advanced use cases.

### Product goals and Non-goals
Goals: provide idempotent index setup nodes, a simplified hybrid search node, and a clearer module structure. Non-goals: fully automating data ingestion, managing Atlas cluster configuration, or replacing the generic MongoDB node for all operations.

## PRODUCT DEFINITION
### Requirements
- Convert `src/orcheo/nodes/mongodb.py` into a module directory at `src/orcheo/nodes/integrations/databases/mongodb/` with a proper `__init__.py` and a base file containing current functionality.
- Preserve public imports with compatibility exports (e.g., `src/orcheo/nodes/mongodb.py` re-exporting from the new path, plus `src/orcheo/nodes/__init__.py`).
- Add two index management nodes:
  - Ensure full-text search index (create if missing, optionally update on mismatch).
  - Ensure vector search index (create if missing, optionally update on mismatch).
- Add a hybrid search node that accepts text query + vector inputs and hides pipeline boilerplate.
- Expose clear inputs/outputs with pydantic validation and descriptive docstrings.
- Update `examples/mongodb.py` to demonstrate index creation + hybrid search usage.

### Designs (if applicable)
Not applicable for UI; see `project/mongodb/2_design.md` for system design.

### Other Teams Impacted
- Documentation/Examples: updated MongoDB example.
- QA/CI: new tests for node behavior and pipeline generation.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
- `src/orcheo/nodes/integrations/databases/mongodb/` becomes a module directory.
- `base.py` retains current `MongoDBNode` and wrappers.
- `search.py` (or similar) contains the new index/hybrid search nodes.
- `src/orcheo/nodes/integrations/databases/mongodb/__init__.py` re-exports public symbols for internal use; compatibility exports stay in `src/orcheo/nodes/mongodb.py` and `src/orcheo/nodes/__init__.py`.

### Technical Requirements
- All MongoDB nodes must use absolute imports and maintain mypy/ruff compliance.
- Index nodes must call `list_search_indexes` before creating/updating indexes.
- Hybrid search node must build a stable, deterministic pipeline and return a normalized result list.
- Changes must include tests under `tests/nodes/` mirroring new modules.

### AI/ML Considerations (if applicable)
Vector index parameters must align with embedding model dimensions; input validation should enforce this.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|---------------------|
| Example usability | New example runs without manual pipeline construction |
| Boilerplate reduction | Fewer lines in example and workflows |
| Maintenance | MongoDB node file length reduced by splitting into module files |

### Rollout Strategy
Ship in a single release with updated imports and examples; provide compatibility re-exports.

### Experiment Plan (if applicable)
Not applicable.

## HYPOTHESIS & RISKS
Hybrid search and index management nodes will significantly reduce workflow setup time and errors. Risks include mismatch between index definitions and actual Atlas configuration; mitigate by clear error messages and optional update/rebuild modes.

## APPENDIX
None.
