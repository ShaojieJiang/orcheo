# Requirements Document: WeCom Event Agent

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** WeCom Event Agent Workflow
- **Type:** Feature
- **Summary:** WeCom Customer Service workflow to create/update events, capture RSVPs, and fetch RSVP lists with MongoDB storage.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-01-02

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| WeCom App Setup | https://open.work.weixin.qq.com/wwopen/manual/detail?t=selfBuildApp | WeCom | Official Docs |
| WeCom Customer Service Overview | https://developer.work.weixin.qq.com/document/path/94638 | WeCom | Customer Service Setup |
| WeCom Customer Service Sync | https://developer.work.weixin.qq.com/document/path/94670 | WeCom | sync_msg API |
| WeCom Callback Verification | https://developer.work.weixin.qq.com/document/path/90930 | WeCom | Callback Verification |
| WeCom Bot Responder Requirements | [../wecom_bot_responder/1_requirements.md](../wecom_bot_responder/1_requirements.md) | Shaojie Jiang | WeCom Bot Responder Requirements |
| WeCom Bot Responder Design | [../wecom_bot_responder/2_design.md](../wecom_bot_responder/2_design.md) | Shaojie Jiang | WeCom Bot Responder Design |
| WeCom Bot Responder Plan | [../wecom_bot_responder/3_plan.md](../wecom_bot_responder/3_plan.md) | Shaojie Jiang | WeCom Bot Responder Plan |

## PROBLEM DEFINITION
### Objectives
Deliver a WeCom workflow that can create or update events, record RSVPs, and list current RSVPs through chat messages. The workflow must validate and decrypt WeCom callbacks, parse user requests, persist data in MongoDB, and reply via Customer Service or internal WeCom messaging.

### Target users
External WeChat users messaging the enterprise Customer Service account, internal WeCom users, and operators who manage the WeCom app and workflow configuration.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Event organizer | Create or edit an event by chat | I can manage event details without a separate UI | P0 | Event record is created/updated with title, description, date, location, and host metadata |
| Attendee | Send an RSVP via chat | My attendance status is captured | P0 | RSVP entry is created/updated with status and timestamp |
| Operator | Request RSVP list for an event | I can follow up with attendees | P1 | Workflow returns a list of RSVPs for the specified event |
| Attendee | Request an event list by chat | I can find an event to attend | P1 | Workflow returns a list of recent events with IDs |

### Context, Problems, Opportunities
WeCom Customer Service provides a chat-based entry point for lightweight event coordination. A workflow that combines WeCom callback handling with MongoDB persistence allows teams to track event metadata and RSVPs without additional infrastructure. This builds on the existing WeCom bot responder patterns while adding structured event and RSVP storage.

### Product goals and Non-goals
**Goals:** Customer Service integration for event operations, reliable callback validation/decryption, clear chat responses, and MongoDB-backed event/RSVP storage.

**Non-goals:** Calendar invitations, reminder scheduling, or complex event analytics.

## PRODUCT DEFINITION
### Requirements
**P0 (must have)**
- WeCom webhook handling uses the same signature validation/decryption flow as the WeCom bot responder.
- Customer Service callbacks are parsed, and the latest text message is extracted for processing.
- Internal WeCom direct messages are processed with the same command parsing and persistence logic as Customer Service messages.
- Commands supported via Customer Service messages:
  - Update Event: create/update events with title, description, ISO date, location, and host metadata, generating IDs when missing.
  - Update RSVP: create/update attendee status (yes/no/maybe/cancelled) with timestamps.
  - Get Event RSVPs: return the current RSVP list for an event.
  - List Events: return a list of recent events with IDs.
- Events and RSVPs stored in MongoDB collections.
- Workflow replies via Customer Service with confirmation or RSVP list.
- Example workflow script provided at `examples/wecom_event_agent/workflow.py` with a README and config file.

**P1 (nice to have)**
- Friendly error replies when required fields are missing.
- Optional response formatting improvements (e.g., sorted lists).

### Designs (if applicable)
See [2_design.md](2_design.md) for the Orcheo workflow design.

### [Optional] Other Teams Impacted
- None identified.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
The workflow receives WeCom Customer Service callbacks, validates the signature, decrypts the payload, and syncs the latest CS message. An AI agent parses the request into a structured command. MongoDB operations store or retrieve event/RSVP data. The workflow returns a reply via WeCom Customer Service.

### Technical Requirements
- WeCom callback verification using Token, EncodingAESKey, and the callback signature params.
- Customer Service sync using access tokens from corp ID and secret.
- MongoDB collections for events and RSVPs with upsert semantics.
- Timestamp handling (created_at/updated_at) for event and RSVP updates.
- Secrets stored in Orcheo vault: `wecom_corp_secret`, `wecom_token`, `wecom_encoding_aes_key`, `mdb_connection_string`.

### AI/ML Considerations (if applicable)
#### Data Requirements
WeCom message content from Customer Service callbacks is used to extract structured commands. No long-term storage of raw messages is required beyond event/RSVP data.

#### Algorithm selection
Use a chat model with a structured JSON prompt to parse event and RSVP intents.

#### Model performance requirements
The parser should return valid JSON for at least 95% of test prompts, with graceful fallback messaging when parsing fails.

## MARKET DEFINITION (for products or large features)
Not applicable; this is an internal workflow.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] Event update success | 95%+ of event update messages stored in MongoDB |
| [Secondary] RSVP update success | 95%+ of RSVP updates stored with timestamps |
| [Secondary] Reply delivery | 95%+ Customer Service replies delivered |

### Rollout Strategy
Validate in a staging WeCom app, then enable the workflow in production once MongoDB and vault secrets are verified.

### Experiment Plan (if applicable)
Not applicable.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Staging app | Validate callbacks, parsing, and MongoDB persistence |
| **Phase 2** | Production app | Enable for end users and monitor errors |

## HYPOTHESIS & RISKS
- **Hypothesis:** A chat-driven workflow can reliably capture event metadata and RSVPs without a separate UI.
- **Risk:** Parsing errors could store incomplete event data.
  - **Mitigation:** Validate required fields and return clear error responses.
- **Risk:** WeCom callback verification failures could block message processing.
  - **Mitigation:** Reuse proven validation/decryption flow from the bot responder and log failures.

## APPENDIX
### Example Commands
- Update event: "Team sync on 2025-03-20 at HQ. Host: Alex. Agenda: roadmap."
- RSVP: "RSVP yes for event 1234"
- Get RSVPs: "Get RSVPs for event 1234"
- List events: "Show me upcoming events"
