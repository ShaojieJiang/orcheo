# Project Plan

## For MongoDB node modularization and hybrid search nodes

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2026-02-02
- **Status:** Approved

---

## Overview

Plan to modularize MongoDB nodes under a shared integrations tree and introduce dedicated index management + hybrid search nodes, with updated examples and tests. This plan depends on the requirements and design documents in `project/mongodb/`.

**Related Documents:**
- Requirements: project/mongodb/1_requirements.md
- Design: project/mongodb/2_design.md

---

## Milestones

### Milestone 1: Project setup and approvals

**Description:** Confirm requirements and design details before implementation.

#### Task Checklist

- [ ] Task 1.1: Review and approve requirements document
  - Dependencies: None
- [ ] Task 1.2: Review and approve design document
  - Dependencies: Task 1.1
- [ ] Task 1.3: Decide index comparison strategy (strict vs. lax)
  - Dependencies: Task 1.2

---

### Milestone 2: Implementation

**Description:** Implement module restructure and new nodes.

#### Task Checklist

- [ ] Task 2.1: Convert `src/orcheo/nodes/mongodb.py` into `src/orcheo/nodes/integrations/databases/mongodb/` with `base.py` and `__init__.py`
  - Dependencies: Milestone 1
- [ ] Task 2.2: Add search nodes in `src/orcheo/nodes/integrations/databases/mongodb/search.py`
  - Dependencies: Task 2.1
- [ ] Task 2.3: Add compatibility exports (`src/orcheo/nodes/mongodb.py`, `src/orcheo/nodes/__init__.py`) to keep imports stable
  - Dependencies: Task 2.1

---

### Milestone 3: Tests and examples

**Description:** Update tests and examples to validate new behavior.

#### Task Checklist

- [ ] Task 3.1: Add unit tests for index management and pipeline generation
  - Dependencies: Milestone 2
- [ ] Task 3.2: Update `examples/mongodb.py` to show advanced usage
  - Dependencies: Task 2.2
- [ ] Task 3.3: Run lint and targeted tests
  - Dependencies: Task 3.1, Task 3.2

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-02 | Codex | Update tasks for integrations tree paths and compatibility exports |
| 2026-02-02 | Codex | Initial draft |
