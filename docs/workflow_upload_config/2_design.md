# Design Document

## For Workflow Upload Runnable Config

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-21
- **Status:** Draft

---

## Overview

This feature adds upload-time runnable configuration so workflow authors can set default runtime settings without baking them into scripts. The CLI gains `--config` and `--config-file` options that behave the same as `orcheo workflow run`, including JSON validation and mutual exclusion. Uploads can now carry tags, metadata, concurrency limits, and other `RunnableConfig` fields as part of the workflow version record.

The runnable config is persisted alongside the workflow version in the configured repository backend (SQLite by default; in-memory only for tests/dev). Workflow runs can merge stored config with per-run overrides, ensuring stored values apply unless explicitly overridden.

The design is intentionally narrow: it reuses the same runnable config parsing/validation as workflow runs and only expands upload payloads and storage, avoiding new config schemas or runtime behavior changes beyond merge precedence. The config is stored with workflow versions (the workflow versions table payload), separate from Agentensor checkpoint tables.

## Components

- **CLI Upload Command (packages/sdk)**
  - Adds `--config` and `--config-file` flags to `orcheo workflow upload`.
  - Reuses the existing runnable config JSON parser (`_resolve_runnable_config`) to enforce object payloads consistently with `workflow run`.
- **SDK Upload Service (packages/sdk)**
  - Accepts the parsed config and forwards it to the appropriate upload API.
  - Supports both JSON workflow uploads and LangGraph script ingestion.
- **Workflow API (apps/backend)**
  - Extends workflow version creation and ingestion requests to accept a runnable config payload.
  - Validates with `RunnableConfigModel` and returns the stored config in responses and workflow show output.
- **Repository Storage (apps/backend)**
  - Persists the runnable config in the workflow versions table (payload JSON) so it is available per version in the configured repository backend (SQLite by default).
- **Execution Layer (apps/backend)**
  - Merges stored config with run-supplied config; run config wins on conflict.

## Request Flows

### Flow 1: JSON Workflow Upload with Config

1. User runs `orcheo workflow upload workflow.json --config '{...}'`.
2. CLI parses the JSON config using the same rules as `workflow run`.
3. SDK upload sends the workflow payload and runnable config to `/api/workflows` (or `/api/workflows/{id}` for updates).
4. Backend validates the config, persists it on the workflow version record, and returns the new version.

### Flow 2: LangGraph Script Upload with Config

1. User runs `orcheo workflow upload workflow.py --config-file config.json`.
2. CLI validates the config file and passes it to the SDK ingestion request.
3. Backend ingests the script at `/api/workflows/{id}/versions/ingest`, attaching the runnable config to the version.
4. The version payload stores the runnable config for that version.

### Flow 3: Workflow Run with Stored Config

1. User triggers a run with optional per-run config.
2. Backend loads the workflow version runnable config from storage.
3. Runtime merges stored config with run config, applying run config precedence.
4. Execution proceeds with the merged config and is stored with the run record.

## API Contracts

```
POST /api/workflows
Body:
  name: string
  graph: object
  metadata: object (optional)
  runnable_config: object (optional)

Response:
  201 Created -> WorkflowVersion payload including runnable_config
  400 -> validation errors for config or payload
```

```
POST /api/workflows/{workflow_id}/versions/ingest
Body:
  script: string
  entrypoint: string (optional)
  metadata: object (optional)
  notes: string (optional)
  created_by: string
  runnable_config: object (optional)

Response:
  201 Created -> WorkflowVersion payload including runnable_config
  400 -> validation errors for config or payload
```

The CLI flags are mutually exclusive: `--config` and `--config-file` cannot be provided together. Config payloads must be JSON objects compatible with `RunnableConfigModel`.

## Data Models / Schemas

| Field | Type | Description |
|-------|------|-------------|
| runnable_config | object | Stored `RunnableConfig` for the workflow version; saved with version payload |

Example payload snippet:

```json
{
  "name": "SupportBot",
  "graph": {"nodes": [], "edges": []},
  "runnable_config": {
    "tags": ["support", "v1"],
    "metadata": {"owner": "cx"},
    "max_concurrency": 4,
    "recursion_limit": 25
  }
}
```

## Security Considerations

- Validate configs with `RunnableConfigModel` and reject non-object JSON.
- Document that secrets should not be stored in runnable configs.
- Ensure stored config is scoped to the workflow version and respects existing auth controls.

## Performance Considerations

- Minimal overhead: config validation is small and stored alongside existing payloads.
- Merge logic should be deterministic and avoid deep-copying large configs unnecessarily.

## Testing Strategy

- **Unit tests**: config parsing and mutual exclusion at the CLI layer.
- **Integration tests**: upload endpoints accept and return runnable config for both JSON and script ingestion.
- **Repository tests**: persisted runnable config in the configured repository backend (SQLite default).
- **Regression tests**: workflow runs without config remain unchanged; run config overrides defaults correctly.

## Rollout Plan

1. Phase 1: Ship API and repository changes in staging; validate persistence and retrieval.
2. Phase 2: Enable CLI flags and update docs; test with internal workflows.
3. Phase 3: Release to all users.

Include backward compatibility for older versions without stored runnable config.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-21 | Codex | Initial draft |
