# Project Plan

## For Slack News Push Workflow

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-20
- **Status:** Approved

---

## Overview

Deliver an Orcheo-native workflow that matches the existing n8n Slack news push automation, including scheduled and Slack-mention triggers, MongoDB queries, formatting, Slack delivery, and read-state updates.

**Related Documents:**
- Requirements: [requirements.md](requirements.md)
- Design: [design.md](design.md)

---

## Milestones

### Milestone 1: Workflow Mapping and Specs

**Description:** Translate the n8n workflow into Orcheo nodes and define any new node subclasses needed for parity.

#### Task Checklist

- [x] Task 1.1: Map each n8n node to an Orcheo node and identify gaps (Slack webhook + parser, MongoDBNode extensions and wrappers).
  - Dependencies: None
- [x] Task 1.2: Define configuration schema and state outputs (channel ID, schedule, item limit, formatting outputs).
  - Dependencies: Task 1.1
- [x] Task 1.3: Document acceptance criteria and error-handling expectations.
  - Dependencies: Task 1.1

---

### Milestone 2: Node and Workflow Implementation

**Description:** Build the new nodes, assemble the Orcheo workflow, and document usage.

#### Task Checklist

- [x] Task 2.1: Implement WebhookTriggerNode configuration plus SlackEventsParserNode with signature validation and `app_mention` filtering.
  - Dependencies: Milestone 1
- [x] Task 2.2: Extend `MongoDBNode` with typed operation inputs and add wrapper nodes for aggregate/find/update operations.
  - Dependencies: Milestone 1
- [x] Task 2.3: Implement the formatter node and compose the workflow graph with sequential Slack post then update.
  - Dependencies: Task 2.2
- [x] Task 2.4: Add docs and example configuration for secrets and channel IDs.
  - Dependencies: Task 2.3

---

### Milestone 3: Validation and Rollout

**Description:** Validate parity with the n8n workflow and enable production schedule.

#### Task Checklist

- [x] Task 3.1: Run unit and integration tests for the formatter plus the extended `MongoDBNode` and wrapper nodes.
  - Dependencies: Milestone 2
- [ ] Task 3.2: Perform manual QA in a staging Slack channel and verify read updates.
  - Dependencies: Task 3.1
- [ ] Task 3.3: Enable the daily schedule and monitor delivery metrics for one week.
  - Dependencies: Task 3.2

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-20 | Codex | Initial draft |
