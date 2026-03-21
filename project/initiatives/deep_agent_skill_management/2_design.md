# Design Document

## For Deep Agent Skill Management — Skills-Aware Deep Agents for Orcheo

- **Version:** 0.1
- **Author:** Claude
- **Date:** 2026-03-21
- **Status:** Approved

---

## Overview

This initiative adds two interconnected capabilities to Orcheo:

1. **Agent Skills CLI** — an `orcheo skill` command group for managing Agent Skills stored in `~/.orcheo/skills/`. Skills follow the open Agent Skills specification: a directory containing a `SKILL.md` file with YAML frontmatter and Markdown instructions, plus optional scripts, references, and assets.

2. **DeepAgentNode** — a new Orcheo node wrapping `create_deep_agent` from the `deepagents` package for autonomous multi-step research with built-in planning, file-system, sub-agent, and summarisation middleware.

3. **Default skill loading** — the integration layer where `DeepAgentNode` automatically discovers and loads all installed skills when no explicit `skills` list is configured, making deep agents skills-aware out of the box.

The implementation follows existing architectural patterns: skills use the same patterns as `orcheo plugin`, and DeepAgentNode extends `AINode` like `AgentNode`. The skill library in `src/orcheo/skills/` is shared between the CLI and the node.

## Components

- **Core Skill Library (`src/orcheo/skills/`)**
  - `models.py` — Data models: `SkillMetadata` (parsed SKILL.md frontmatter), `SkillRecord` (installed skill state), `SkillValidationError`.
  - `paths.py` — Storage path helpers: `get_skills_dir()`, `build_skill_paths()`. Respects `ORCHEO_SKILLS_DIR` env var.
  - `parser.py` — SKILL.md frontmatter parser and validator. Extracts YAML frontmatter, validates name/description constraints per the Agent Skills specification.
  - `manager.py` — `SkillManager` class: install, uninstall, list, show, validate operations. Manages `skills.toml` state file and skill directory lifecycle. Also exposes `get_installed_skill_paths()` for use by nodes.

- **SDK Services Layer (`packages/sdk/src/orcheo_sdk/services/skills.py`)**
  - Thin service functions: `list_skills_data()`, `show_skill_data()`, `install_skill_data()`, `uninstall_skill_data()`, `validate_skill_data()`.
  - Instantiates `SkillManager` and delegates to it.

- **CLI Commands (`packages/sdk/src/orcheo_sdk/cli/skill.py`)**
  - `orcheo skill list` — tabular display of installed skills.
  - `orcheo skill show <name>` — detailed skill metadata and file listing.
  - `orcheo skill install <ref>` — install from local path.
  - `orcheo skill uninstall <name>` — remove skill.
  - `orcheo skill validate <path>` — validate without installing.

- **DeepAgentNode (`src/orcheo/nodes/deep_agent.py`)**
  - Extends `AINode` with deep-research configuration fields.
  - Uses `create_deep_agent` from the `deepagents` package.
  - `_resolve_skills()` method: when `self.skills` is `None`, calls `SkillManager.get_installed_skill_paths()` to discover all installed skill directories; when set explicitly, uses those paths directly.
  - Tool preparation reuses the same pattern as `AgentNode._prepare_tools()`.
  - Result is returned in the standard `AINode` format (wrapped in messages key).

## Request Flows

### Flow 1: Install a skill from local path

1. User runs `orcheo skill install ./my-skill/`.
2. CLI invokes `install_skill_data("./my-skill/")`.
3. `SkillManager.install()` validates the path contains a `SKILL.md` file.
4. Parser extracts and validates YAML frontmatter (name, description, optional fields).
5. Validates that the skill name matches the directory name.
6. Checks for name conflicts with existing installations.
7. Copies the skill directory to `~/.orcheo/skills/<name>/`.
8. Appends a `SkillRecord` to `skills.toml`.
9. Returns the installed skill metadata.

### Flow 2: DeepAgentNode with auto-discovered skills

1. Graph builder instantiates `DeepAgentNode` from JSON config (no `skills` field set).
2. `AINode.__call__` invokes `resolved_for_run()` to decode variable templates.
3. `DeepAgentNode.run()` calls `_prepare_tools()` to resolve tools.
4. `DeepAgentNode.run()` calls `_resolve_skills()` — since `self.skills` is `None`, it discovers all installed skill directories from `~/.orcheo/skills/` via `SkillManager.get_installed_skill_paths()`.
5. Node builds a combined system prompt from `system_prompt` and `research_prompt`.
6. Node calls `create_deep_agent(model, tools, system_prompt, skills=resolved_skill_paths, ...)`.
7. Agent executes autonomously with built-in middleware and loaded skills.
8. Final agent result is returned and serialized by `AINode.__call__`.

### Flow 3: DeepAgentNode with explicit skills

1. User sets `"skills": ["/path/to/custom-skill"]` in the node config.
2. `_resolve_skills()` detects `self.skills` is not `None` and returns the explicit list.
3. Only the specified skills are passed to `create_deep_agent`.

### Flow 4: List installed skills

1. User runs `orcheo skill list`.
2. CLI invokes `list_skills_data()`.
3. `SkillManager.list_skills()` reads `skills.toml` and scans `~/.orcheo/skills/`.
4. For each installed skill, reads `SKILL.md` frontmatter to get current name and description.
5. Returns list of skill summaries.

## API Contracts

### CLI Commands

```
orcheo skill list
  Output: Table with columns [Name, Description, Source, Installed]

orcheo skill show <name>
  Output: JSON/Rich panel with all metadata fields and file listing

orcheo skill install <ref>
  Args: ref — local directory path
  Output: Installed skill metadata

orcheo skill uninstall <name>
  Args: name — installed skill name
  Output: Confirmation message

orcheo skill validate <path>
  Args: path — directory containing SKILL.md
  Output: Validation result (pass/fail with errors)
```

### DeepAgentNode JSON Schema (workflow config)

```json
{
  "type": "DeepAgentNode",
  "name": "research_agent",
  "ai_model": "openai:gpt-4o",
  "system_prompt": "You are a research assistant.",
  "research_prompt": "Plan your research steps before executing.",
  "predefined_tools": ["web_search", "document_reader"],
  "mcp_servers": {},
  "max_iterations": 15,
  "skills": null
}
```

When `skills` is `null` or omitted, all installed skills from `~/.orcheo/skills/` are loaded automatically.

## Data Models / Schemas

### SkillMetadata (parsed from SKILL.md)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | 1-64 chars, lowercase alphanumeric + hyphens |
| `description` | str | Yes | 1-1024 chars, non-empty |
| `license` | str \| None | No | License name or reference |
| `compatibility` | str \| None | No | Max 500 chars, environment requirements |
| `metadata` | dict[str, str] \| None | No | Arbitrary key-value pairs |
| `allowed_tools` | str \| None | No | Space-delimited pre-approved tools |

### SkillRecord (persisted in skills.toml)

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Skill name (matches directory name) |
| `source` | str | Original install path/URL |
| `installed_at` | str | ISO 8601 timestamp |
| `description` | str | Skill description from SKILL.md |

### DeepAgentNode Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | str | (required) | Node name in the workflow |
| `ai_model` | str | (required) | Chat model identifier |
| `system_prompt` | str \| None | None | Base system prompt |
| `research_prompt` | str \| None | None | Research-specific instructions appended to system prompt |
| `predefined_tools` | list[str] | [] | Orcheo tool registry names |
| `workflow_tools` | list[WorkflowTool] | [] | Sub-workflow tools |
| `mcp_servers` | dict[str, Any] | {} | MCP server connections |
| `max_iterations` | int | 100 | Recursion limit for the agent |
| `model_kwargs` | dict[str, Any] | {} | Additional kwargs for init_chat_model |
| `response_format` | dict \| type[BaseModel] \| None | None | Structured output format |
| `skills` | list[str] \| None | None | Skill paths; `None` = auto-discover from installed skills |
| `memory` | list[str] \| None | None | Memory file paths (AGENTS.md) loaded at startup |
| `debug` | bool | False | Enable deep-agent debug mode |

## Security Considerations

- Skills are local files — no network access required for installed skills.
- Skill scripts are not auto-executed — they are only run when an agent explicitly invokes them.
- `orcheo skill validate` helps users vet skills before installation.
- Same credential resolution as `AgentNode` — no new attack surface.
- `max_iterations` provides a hard bound on agent execution depth.
- Tool access is explicitly configured — no implicit tool discovery beyond skills.

## Performance Considerations

- Skills are filesystem-based: listing and showing are I/O-bound, not compute-bound.
- `skills.toml` is read once per CLI invocation — no caching needed.
- Skill discovery at node runtime scans `~/.orcheo/skills/` for subdirectories — fast for typical installations (< 50 skills).
- Deep research agents can run for extended periods. `max_iterations` default of 100 keeps execution bounded.
- Loading many installed skills increases the agent's context. Users can limit this by setting `skills` explicitly.

## Testing Strategy

- **Unit tests**:
  - `parser.py`: SKILL.md parsing (valid/invalid frontmatter, all field validations, edge cases).
  - `manager.py`: install, uninstall, list, show, validate operations; `get_installed_skill_paths()`.
  - `models.py`: data model construction and defaults.
  - `paths.py`: default paths, env var override.
  - `services/skills.py`: service function delegation.
  - `cli/skill.py`: CLI output formatting, error handling.
  - `deep_agent.py`: node construction, system prompt building, tool preparation, `_resolve_skills()` (auto-discovery and explicit), run execution with skills forwarded, registry entry.

- **Integration tests**:
  - Install skill → verify DeepAgentNode auto-discovers it (temp directory round-trip).

## Rollout Plan

1. Phase 1: Core skill library (`src/orcheo/skills/`) and unit tests.
2. Phase 2: SDK services and CLI commands with tests.
3. Phase 3: DeepAgentNode implementation with tests.
4. Phase 4: Integration — `_resolve_skills()` auto-discovery and tests.
5. Phase 5: Documentation and example workflows.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-03-21 | Claude | Initial draft — merged from separate agent_skills and deep_agent_node designs |
