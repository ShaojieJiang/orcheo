# Project Plan

## For WeCom Bot Responder Workflow

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-28
- **Status:** Approved

---

## Overview

Deliver a minimal WeCom bot responder workflow that validates callbacks, decrypts payloads, and replies to direct messages with a fixed response.

**Related Documents:**
- Requirements: [1_requirements.md](1_requirements.md)
- Design: [2_design.md](2_design.md)

---

## Milestones

### Milestone 1: Direct-Message Response MVP

**Description:** Build the direct-message responder flow with validation and a fixed reply.

#### Task Checklist

- [x] Task 1.1: Define the fixed reply payload and configuration inputs (corp ID, agent ID, reply text).
  - Dependencies: None
- [x] Task 1.2: Define validation/decryption inputs (Token, EncodingAESKey) and optional message type configuration.
  - Dependencies: Task 1.1
- [x] Task 1.3: Wire the WeCom webhook trigger to the parser and reply sender.
  - Dependencies: Task 1.2
- [x] Task 1.4: Document WeCom app setup, callback URL, vault secrets, and local HTTPS tunnel setup.
  - Dependencies: Task 1.3

---

### Milestone 2: Hardening and Validation

**Description:** Improve reliability and observability for production use.

#### Task Checklist

- [x] Task 2.1: Add unit tests for signature validation and direct-message filtering.
  - Dependencies: Milestone 1
- [x] Task 2.2: Add integration test for message delivery (mocked WeCom API).
  - Dependencies: Task 2.1
- [x] Task 2.3: Add optional allowlist of user IDs.
  - Dependencies: Task 2.1
- [x] Task 2.4: Add structured logging for validation failures and message delivery status.
  - Dependencies: Task 2.1

---

### Milestone 3: Rollout

**Description:** Validate in staging and enable production.

#### Task Checklist

- [x] Task 3.1: Perform manual QA in a staging WeCom app.
  - Dependencies: Milestone 2
- [x] Task 3.2: Enable the workflow in production and monitor delivery metrics.
  - Dependencies: Task 3.1

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-28 | Codex | Initial draft |
