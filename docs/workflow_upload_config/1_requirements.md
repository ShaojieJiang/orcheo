# Requirements Document

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** Workflow Upload Runnable Config
- **Type:** Enhancement
- **Summary:** Allow workflow uploads to accept runnable configs via `--config` or `--config-file` and persist them per workflow version in the configured repository (SQLite by default).
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-21

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| CLI Reference | README.md | Shaojie Jiang | CLI commands and `workflow run` config options |
| Design Review | docs/workflow_upload_config/2_design.md | Shaojie Jiang | Workflow upload config design |
| Eng Requirement Doc | docs/workflow_upload_config/1_requirements.md | Shaojie Jiang | Workflow upload config requirements |
| Project Plan | docs/workflow_upload_config/3_plan.md | Shaojie Jiang | Workflow upload config plan |

## PROBLEM DEFINITION
### Objectives
Enable `orcheo workflow upload` to accept `--config` and `--config-file` with the same semantics as `orcheo workflow run`. Persist the provided runnable config in the workflow version storage (configured repository backend, SQLite by default) so uploads can carry default configuration without hard-coding it in scripts.

### Target users
Workflow authors and operators who want stable defaults for runtime config (tags, metadata, concurrency, prompts) and repeatable uploads.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Workflow author | Upload a workflow with `--config` or `--config-file` | I can set default runtime configuration without editing code | P0 | Upload validates JSON object input, stores config with the new workflow version, and reports success |
| Operator | View stored config in workflow show output | I can audit and reproduce runs | P0 | Workflow show output includes the stored runnable config from the latest version |
| Workflow author | Override defaults on run | I can use per-run overrides when needed | P1 | Run config merges with stored runnable config, with explicit run config taking precedence |

### Context, Problems, Opportunities
`orcheo workflow run` supports `--config` and `--config-file`, but `orcheo workflow upload` does not. Authors must either bake defaults into Python scripts or pass config on every run, which leads to duplicated settings and drift. Allowing uploads to include runnable config improves repeatability, keeps code cleaner, and ensures the config is preserved alongside the workflow version in storage.

### Product goals and Non-goals
Goals: provide upload-time config inputs equivalent to run-time inputs; persist runnable config in the workflow version store; expose it via version APIs and workflow show output for audit and reuse; keep backward compatibility for uploads without config. Non-goals: redesigning workflow execution UI, adding new config schema fields beyond existing `RunnableConfig`, or migrating historical scripts to strip embedded config.

## PRODUCT DEFINITION
### Requirements
- **P0: Upload-time config inputs**
  - Add `--config` and `--config-file` to `orcheo workflow upload` with the same JSON parsing and mutual-exclusion rules as `workflow run`.
  - Accept config for both JSON workflow uploads and LangGraph script ingestion.
- **P0: Persisted runnable config**
  - Store the provided runnable config in the workflow version record within the configured repository backend (SQLite by default). In tests/dev, the in-memory repository stores it only for the lifetime of the process.
  - Include the stored config in workflow version responses and workflow show output.
- **P1: Runtime merge behavior**
  - When executing a run, merge stored runnable config with per-run config so overrides win while preserving stored values.
- **P1: Documentation**
  - Update README and workflow upload documentation to show examples of `--config` and `--config-file`.

### Designs (if applicable)
See docs/workflow_upload_config/2_design.md for architecture and API details, including [API Contracts](2_design.md#api-contracts), [Data Models / Schemas](2_design.md#data-models--schemas), [Error Scenarios](2_design.md#error-scenarios), and [Rollback Plan](2_design.md#rollback-plan).

## TECHNICAL CONSIDERATIONS
### Architecture Overview
The CLI resolves config input and forwards it to the SDK upload flow. The backend validates the payload using the existing runnable config model and persists the config with the workflow version in the configured repository backend (SQLite by default). Workflow runs can read and merge the stored runnable config with per-run overrides.

### Technical Requirements
- Reuse `RunnableConfigModel` validation and JSON parsing rules for upload-time config.
- Store config in the workflow_versions.payload.runnable_config field in the configured repository backend (SQLite by default). In tests/dev, the in-memory repository stores it only for the lifetime of the process.
- Maintain backward compatibility for uploads without config and for older version payloads without stored runnable config.
- Provide deterministic merge precedence: run config overrides stored runnable config on conflicts.

## MARKET DEFINITION
Internal feature; no external market analysis required.

## LAUNCH/ROLLOUT PLAN

### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| Primary: Uploads with config succeed | >=99% success rate on CLI uploads using config |
| Secondary: Stored config visibility | 100% of uploaded configs appear in version payloads |
| Guardrail: Runtime behavior | No regression in runs without config and no config merge errors |

### Rollout Strategy
Ship the CLI and API changes together behind a minor release; validate in staging with a few internal workflows before enabling for general use.

### Experiment Plan (if applicable)
Not applicable.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Internal workflows | Enable upload config in staging; verify persistence and merge behavior |
| **Phase 2** | All environments | Release to users with updated docs and examples |

## HYPOTHESIS & RISKS
Adding runnable config to workflow uploads will reduce script churn and improve reproducibility. Risks include storing sensitive values in configs and confusing precedence between stored configs and per-run overrides. Mitigation: validation via `RunnableConfigModel`, clear CLI messaging about precedence, and documentation warning against embedding secrets.

## APPENDIX
None.
