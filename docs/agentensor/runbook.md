# Agentensor Training Runbook

## Overview
- Training runs are dispatched over the existing workflow websocket (`type: "train_workflow"`). Payload mirrors evaluation but accepts a `training` block with dataset/evaluators plus optimizer settings (`epochs`, `checkpoint_interval`, `case_timeout_seconds`, `max_concurrency`).
- AgentensorNode enforces guardrails: concurrency is capped at 8 (or the requested `max_concurrency`, whichever is lower) and case timeouts default to 30s (max 300s).
- Checkpoints are emitted at `checkpoint_interval` boundaries and whenever a new best score is observed. Each checkpoint captures the runnable config (including prompts), metrics, and metadata (`epoch`, summary).

## Storage & Migrations
- **SQLite**: `agentensor_checkpoints` table is auto-created alongside execution history.
  ```
  CREATE TABLE IF NOT EXISTS agentensor_checkpoints (
      id TEXT PRIMARY KEY,
      workflow_id TEXT NOT NULL,
      config_version INTEGER NOT NULL,
      runnable_config TEXT NOT NULL,
      metrics TEXT NOT NULL,
      metadata TEXT NOT NULL DEFAULT '{}',
      artifact_url TEXT,
      is_best INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_agentensor_checkpoints_workflow
      ON agentensor_checkpoints(workflow_id, config_version);
  CREATE INDEX IF NOT EXISTS idx_agentensor_checkpoints_best
      ON agentensor_checkpoints(workflow_id, is_best);
  ```
- **PostgreSQL**: apply the equivalent DDL before deploying:
  ```
  CREATE TABLE IF NOT EXISTS agentensor_checkpoints (
      id TEXT PRIMARY KEY,
      workflow_id TEXT NOT NULL,
      config_version INTEGER NOT NULL,
      runnable_config JSONB NOT NULL,
      metrics JSONB NOT NULL,
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
      artifact_url TEXT NULL,
      is_best BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE INDEX IF NOT EXISTS idx_agentensor_checkpoints_workflow
      ON agentensor_checkpoints (workflow_id, config_version);
  CREATE INDEX IF NOT EXISTS idx_agentensor_checkpoints_best
      ON agentensor_checkpoints (workflow_id, is_best);
  ```
- **Rollback/restore**: checkpoints are append-only. To roll back a regression, fetch the previous best via `GET /api/workflows/{workflow_id}/agentensor/checkpoints?limit=5`, select the desired `config_version`, and reuse its `runnable_config` in a new run.

## Operations
- Start a training run by streaming:
  ```json
  {
    "type": "train_workflow",
    "graph_config": {...},
    "inputs": {...},
    "training": {
      "dataset": {"cases": [...]},
      "evaluators": [{"id": "quality", "entrypoint": "module:evaluator"}],
      "optimizer": {"epochs": 3, "checkpoint_interval": 1}
    }
  }
  ```
- Monitor progress events:
  - `training_progress`: per-case output/evaluations
  - `training_checkpoint`: persisted checkpoint payload
  - `training_epoch_complete`: summary per epoch
- Download/reuse: `GET /api/workflows/{workflow_id}/agentensor/checkpoints/{checkpoint_id}` returns the stored config and metrics for reuse.

## Performance & Concurrency Checks
- The training node caps `max_concurrency` to 8 and applies wait-for timeouts per case. Increase `checkpoint_interval` to reduce write amplification in long runs.
- For load testing, run concurrent websocket training sessions against SQLite and Postgres backends; verify checkpoint ordering and `is_best` flag consistency. On Postgres, wrap the DDL above in migrations to validate apply/rollback.
