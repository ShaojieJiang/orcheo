# Project Plan

## For WeCom Event Agent Workflow

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-01-02
- **Status:** Draft

---

## Overview

Deliver a WeCom workflow for Customer Service and internal messages that
creates/updates events, captures RSVPs, and lists RSVPs backed by MongoDB
storage. The plan aligns with the WeCom bot responder patterns for validation
and reply delivery.

**Related Documents:**
- Requirements: [1_requirements.md](1_requirements.md)
- Design: [2_design.md](2_design.md)

---

## Milestones

### Milestone 1: Workflow Core and MongoDB Persistence

**Description:** Build the CS workflow path and implement event/RSVP storage.

#### Task Checklist

- [x] Task 1.1: Configure WeCom CS webhook parsing and access token flow.
  - Dependencies: None
- [x] Task 1.2: Implement command parsing for update_event, update_rsvp, get_rsvps.
  - Dependencies: Task 1.1
- [x] Task 1.3: Add MongoDB upsert nodes for events and RSVPs.
  - Dependencies: Task 1.2
- [x] Task 1.4: Add MongoDB RSVP lookup and formatted replies.
  - Dependencies: Task 1.3
- [x] Task 1.5: Add MongoDB event list lookup and formatted replies.
  - Dependencies: Task 1.3

---

### Milestone 2: Reply Handling and Validation

**Description:** Harden the workflow with validation and error responses.

#### Task Checklist

- [x] Task 2.1: Validate required event fields and RSVP fields.
  - Dependencies: Milestone 1
- [x] Task 2.2: Add user-facing error replies for missing data or invalid status.
  - Dependencies: Task 2.1
- [x] Task 2.3: Document example prompts and configuration inputs.
  - Dependencies: Task 2.1

---

### Milestone 3: Example Delivery and QA

**Description:** Deliver the example workflow and run basic verification.

#### Task Checklist

- [x] Task 3.1: Create `examples/wecom_event_agent/workflow.py` and config.
  - Dependencies: Milestone 2
- [x] Task 3.2: Add README with setup steps and test instructions.
  - Dependencies: Task 3.1
- [x] Task 3.3: Run a local CS callback test in staging.
  - Dependencies: Task 3.2

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-01-02 | Codex | Initial draft |
