# Project Plan

## For WeCom News Push Workflow

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-28
- **Status:** Approved

---

## Overview

Deliver an Orcheo-native workflow that matches the Slack digest behavior for WeCom, including scheduled and app-mention triggers, MongoDB queries, formatting, WeCom delivery, and read-state updates.

**Related Documents:**
- Requirements: [1_requirements.md](1_requirements.md)
- Design: [2_design.md](2_design.md)

---

## Milestones

### Milestone 1: Scripted Mentions and Scheduled Messages

**Description:** Deliver the minimal WeCom flow for app mentions, scripted replies, and scheduled scripted messages once per minute to a specified group.

#### Task Checklist

- [x] Task 1.1: Define the scripted reply payload and group-target configuration (chat ID, message template).
  - Dependencies: None
- [x] Task 1.2: Wire the app-mention trigger to a scripted reply sender for WeCom.
  - Dependencies: Task 1.1
- [x] Task 1.3: Configure a once-per-minute schedule to send scripted messages to the specified group.
  - Dependencies: Task 1.1
- [x] Task 1.4: Document how to set the scripted content and target group for both flows.
  - Dependencies: Task 1.2

---

### Milestone 2: Workflow Mapping and Specs

**Description:** Translate the desired Slack-equivalent behavior into WeCom-specific nodes and define any new node subclasses needed for parity.

#### Task Checklist

- [ ] Task 2.1: Map each workflow step to an Orcheo node and identify gaps (WeCom webhook + parser, access token handling, MongoDBNode extensions and wrappers).
  - Dependencies: None
- [ ] Task 2.2: Define configuration schema and state outputs (chat ID, schedule, item limit, formatting outputs).
  - Dependencies: Task 2.1
- [ ] Task 2.3: Document acceptance criteria and error-handling expectations.
  - Dependencies: Task 2.1

---

### Milestone 3: Node and Workflow Implementation

**Description:** Build the new nodes, assemble the Orcheo workflow, and document usage.

#### Task Checklist

- [ ] Task 3.1: Implement WebhookTriggerNode configuration plus WeComEventsParserNode with signature validation, URL verification handling, and `@mention` filtering.
  - Dependencies: Milestone 2
- [ ] Task 3.2: Implement WeComAccessTokenNode and WeComSendMessageNode using the app credentials and target chat routing.
  - Dependencies: Milestone 2
- [ ] Task 3.3: Extend `MongoDBNode` with typed operation inputs and add wrapper nodes for aggregate/find/update operations.
  - Dependencies: Milestone 2
- [ ] Task 3.4: Implement the formatter node and compose the workflow graph with sequential WeCom post then update.
  - Dependencies: Task 3.3
- [ ] Task 3.5: Add docs and example configuration for secrets, callback URL, trusted IPs, and chat IDs.
  - Dependencies: Task 3.4

---

### Milestone 4: Validation and Rollout

**Description:** Validate parity with the Slack digest behavior and enable the production schedule.

#### Task Checklist

- [ ] Task 4.1: Run unit and integration tests for the formatter, WeCom parser, and MongoDB wrapper nodes.
  - Dependencies: Milestone 3
- [ ] Task 4.2: Perform manual QA in a staging WeCom chat and verify read updates.
  - Dependencies: Task 4.1
- [ ] Task 4.3: Enable the daily schedule and monitor delivery metrics for one week.
  - Dependencies: Task 4.2

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-28 | Codex | Initial draft |
