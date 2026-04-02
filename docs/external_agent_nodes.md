# External Agent CLI Nodes

Orcheo can run Claude Code and Codex as workflow nodes through the execution
worker. This feature is intended for self-hosted deployments where the worker
host can safely run external coding-agent CLIs inside validated Git worktrees.

## Support Scope

- Self-hosted only.
- Worker-managed installs only; Orcheo does not install these CLIs into global
  system paths.
- Manual provider login is still required on the worker host.
- V1 does not add new Orcheo environment variables for runtime roots,
  maintenance cadence, or provider selection.

## Runtime Behavior

Orcheo manages provider runtimes under a persistent root with strong defaults:

- Use `/data/agent-runtimes` when `/data` exists and is writable.
- Otherwise use `~/.orcheo/agent-runtimes`.
- In Docker deployments, keep the worker `HOME` on persistent storage so
  provider login state such as `~/.claude*` and `$CODEX_HOME/auth.json`
  survives container restarts.
- Install the latest published provider CLI into a versioned provider-owned
  prefix.
- Keep one current runtime and one previous known-good runtime for rollback and
  debugging.
- Check maintenance on a fixed 7-day cadence.
- Do not perform inline upgrades immediately before executing a workflow step.

Failed maintenance or failed upgrades do not replace the active runtime. New
versions are staged side-by-side and only become current after install
verification succeeds.

## Provider Bootstrap

### Codex

- Package: `@openai/codex`
- Runtime command: `codex exec --full-auto --sandbox workspace-write`
- Manual login:

```bash
codex login
```

- Programmatic auth is also supported through provider-native credentials such
  as `CODEX_API_KEY` or `OPENAI_API_KEY`. Orcheo does not rename or wrap those
  credentials.

### Claude Code

- Package: `@anthropic-ai/claude-code`
- Runtime command: `claude --print ... --permission-mode acceptEdits`
- Manual login:

```bash
claude
```

- Provider-native auth is also supported when the worker environment already
  exposes supported Claude Code credentials such as `ANTHROPIC_API_KEY`.

## Node Contract

Both `ClaudeCodeNode` and `CodexNode` share the same workflow-facing fields:

- `prompt`
- `system_prompt`
- `working_directory`
- `auto_init_git_worktree`
- `timeout_seconds`

By default, Orcheo initializes a Git worktree in `working_directory` when the
path is safe but not yet inside one. Orcheo still rejects `/`, the worker home
directory, and the managed runtime root.

Normalized node output includes:

- `status`
- `provider`
- `resolved_version`
- `command`
- `command_path`
- `working_directory`
- `exit_code`
- `stdout`
- `stderr`
- `reason`
- `message`

If auth is missing, the node returns `status = "setup_needed"` plus exact login
commands and rerun guidance instead of a generic failure.

## Example Snippets

### Codex autofix node

```json
{
  "type": "CodexNode",
  "name": "codex_fix",
  "prompt": "Read the repository, run the targeted tests, make the minimal fix, and stop.",
  "working_directory": "{{inputs.repo_path}}",
  "timeout_seconds": 1800
}
```

### Claude Code review node

```json
{
  "type": "ClaudeCodeNode",
  "name": "claude_review",
  "prompt": "Review the current branch for behavioral regressions and summarize the highest-risk issues.",
  "working_directory": "{{inputs.repo_path}}",
  "timeout_seconds": 1800
}
```

## Canvas Delivery Checklist

Backend support does not automatically make these nodes usable in Canvas. The
frontend delivery checklist is:

- Add `ClaudeCodeNode` and `CodexNode` to the Canvas node catalog.
- Expose `prompt`, `system_prompt`, `working_directory`, and
  `timeout_seconds` through the current node editing surface. Do not rely on
  the deprecated node inspector for external-agent setup actions.
- Add a shared Canvas settings surface for worker-scoped provider readiness and
  OAuth login, because Claude Code and Codex auth belong to the worker host,
  not to individual workflow nodes.
- Label the nodes as self-hosted/execution-worker features.
- Surface setup-needed results so operators can jump to the shared External
  Agents settings flow instead of shelling into the worker manually.
