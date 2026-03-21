# Project Plan

## For Deep Agent Skill Management — Skills-Aware Deep Agents for Orcheo

- **Version:** 0.1
- **Author:** Claude
- **Date:** 2026-03-21
- **Status:** Complete

---

## Overview

Implement the Agent Skills management system, the DeepAgentNode, and their integration so that installed skills are automatically loaded by deep agents. The core skill library, SDK services/CLI, and DeepAgentNode are complete. The remaining work is the integration layer: `DeepAgentNode` should auto-discover installed skills by default.

**Related Documents:**
- Requirements: `project/initiatives/deep_agent_skill_management/1_requirements.md`
- Design: `project/initiatives/deep_agent_skill_management/2_design.md`

---

## Milestones

### Milestone 1: Core Skill Library

**Description:** Implement the core skill library in `src/orcheo/skills/` — data models, path helpers, SKILL.md parser, and skill manager. Achieve 100% test coverage.

**Status:** Complete

#### Task Checklist

- [x] Task 1.1: Create `src/orcheo/skills/__init__.py` — package init with exports
- [x] Task 1.2: Create `src/orcheo/skills/models.py` — `SkillMetadata`, `SkillRecord`, `SkillValidationError` dataclasses
- [x] Task 1.3: Create `src/orcheo/skills/paths.py` — `get_skills_dir()`, `SKILLS_DIR_ENV`, respecting `ORCHEO_SKILLS_DIR` env var
- [x] Task 1.4: Create `src/orcheo/skills/parser.py` — `parse_skill_md()` and `validate_skill_metadata()` for SKILL.md frontmatter
- [x] Task 1.5: Create `src/orcheo/skills/manager.py` — `SkillManager` with install, uninstall, list, show, validate
- [x] Task 1.6: Write unit tests in `tests/skills/` — full coverage for models, paths, parser, and manager
- [x] Task 1.7: Run `make format`, `make lint`, verify 100% coverage on new modules

---

### Milestone 2: SDK Services and CLI Commands

**Description:** Implement the SDK services layer and CLI commands for `orcheo skill`.

**Status:** Complete

#### Task Checklist

- [x] Task 2.1: Create `packages/sdk/src/orcheo_sdk/services/skills.py` — service functions
- [x] Task 2.2: Export skill service functions from `packages/sdk/src/orcheo_sdk/services/__init__.py`
- [x] Task 2.3: Create `packages/sdk/src/orcheo_sdk/cli/skill.py` — `skill_app` Typer group
- [x] Task 2.4: Register `skill_app` in CLI main entry point
- [x] Task 2.5: Write unit tests for services and CLI in `tests/sdk/`
- [x] Task 2.6: Run `make format`, `make lint`, verify 100% coverage on new modules

---

### Milestone 3: DeepAgentNode Implementation

**Description:** Implement the DeepAgentNode class, register it in the node registry, and achieve 100% test coverage.

**Status:** Complete

#### Task Checklist

- [x] Task 3.1: Create `src/orcheo/nodes/deep_agent.py` — implement `DeepAgentNode(AINode)`
- [x] Task 3.2: Implement `_build_system_prompt()` — concatenate system_prompt and research_prompt
- [x] Task 3.3: Implement `_prepare_tools()` — reuse AgentNode pattern
- [x] Task 3.4: Implement `run()` method — create agent with `recursion_limit=max_iterations`
- [x] Task 3.5: Register `DeepAgentNode` in node registry with category `"ai"`
- [x] Task 3.6: Write unit tests in `tests/nodes/test_deep_agent.py`
- [x] Task 3.7: Run `make format`, `make lint`, verify 100% coverage on new module

---

### Milestone 4: Integration — Default Skill Loading

**Description:** Connect the skill system to DeepAgentNode so that installed skills are automatically discovered and loaded when `skills` is not explicitly set.

**Status:** Complete

#### Task Checklist

- [x] Task 4.1: Add `get_installed_skill_paths()` method to `SkillManager` — returns list of absolute paths to all installed skill directories under `~/.orcheo/skills/`
  - Dependencies: Milestone 1
- [x] Task 4.2: Add `_resolve_skills()` method to `DeepAgentNode` — when `self.skills` is `None`, calls `SkillManager(get_skills_dir()).get_installed_skill_paths()` to discover installed skills; when set, returns the explicit list
  - Dependencies: Task 4.1
- [x] Task 4.3: Update `DeepAgentNode.run()` to call `_resolve_skills()` and pass the result to `create_deep_agent(skills=...)`
  - Dependencies: Task 4.2
- [x] Task 4.4: Write unit tests for `get_installed_skill_paths()` in `tests/skills/test_manager.py` — empty dir, populated dir, missing dir, sorted order
  - Dependencies: Task 4.1
- [x] Task 4.5: Write unit tests for `_resolve_skills()` in `tests/nodes/test_deep_agent.py` — auto-discovery (None), explicit list, empty install dir, exception handling
  - Dependencies: Task 4.2
- [x] Task 4.6: Update existing `test_deep_agent.py` tests to account for skill resolution in `run()`
  - Dependencies: Task 4.3
- [x] Task 4.7: Run `make format`, `make lint`, verify 100% coverage on changed modules
  - Dependencies: Tasks 4.4–4.6

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-03-21 | Claude | Initial draft — merged from separate agent_skills and deep_agent_node plans; added Milestone 4 for integration |
