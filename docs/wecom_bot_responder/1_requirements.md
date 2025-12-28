# Requirements Document: WeCom Bot Responder

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** WeCom Bot Responder Workflow
- **Type:** Feature
- **Summary:** Respond to WeCom direct messages with a fixed reply using Orcheo webhook triggers.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-28

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| WeCom App Setup | https://open.work.weixin.qq.com/wwopen/manual/detail?t=selfBuildApp | WeCom | Official Docs |
| Requirements | [1_requirements.md](1_requirements.md) | Shaojie Jiang | WeCom Bot Responder Requirements |
| Design | [2_design.md](2_design.md) | Shaojie Jiang | WeCom Bot Responder Design |
| Plan | [3_plan.md](3_plan.md) | Shaojie Jiang | WeCom Bot Responder Plan |

## PROBLEM DEFINITION
### Objectives
Deliver a WeCom bot that responds to direct messages with a fixed message. The flow must validate WeCom callbacks, decrypt payloads, and reply to the sender reliably.

### Target users
WeCom users who message the app directly and operators who manage the WeCom app and webhook configuration.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| WeCom user | Receive a reply when I message the app | I know the bot is reachable and responsive | P0 | A direct message receives the configured fixed reply |
| Operator | Verify WeCom callbacks are validated and decrypted | I can trust the workflow is secure and stable | P0 | Invalid signatures are rejected and valid callbacks proceed |

### Context, Problems, Opportunities
The previous "news push" workflow is not feasible. Instead, we need a minimal, reliable WeCom bot responder that proves end-to-end webhook handling and messaging.

### Product goals and Non-goals
**Goals:** Direct-message response, reliable WeCom callback validation/decryption, and a configurable fixed reply message.

**Non-goals:** Scheduled pushes, RSS ingestion, MongoDB reads, or content formatting beyond the fixed reply.

## PRODUCT DEFINITION
### Requirements
**P0 (must have)**
- WeCom webhook handling uses a webhook trigger plus a WeCom event parser/validator node.
- Webhook handler supports the WeCom URL verification handshake (GET with `echostr`) and message decryption for encrypted callbacks.
- Only direct messages are processed; group chat messages are ignored.
- Send a fixed response message back to the direct-message sender using WeCom app credentials.
- Return immediate responses for WeCom verification and synchronous checks.
- Respect WeCom platform constraints: HTTPS callback URL, trusted IP allowlist, and access token refresh via corp ID/secret.

**P1 (nice to have)**
- Configurable message type (`text` or `markdown`).
- Optional allowlist of user IDs.

### Designs (if applicable)
See [2_design.md](2_design.md) for the Orcheo workflow design.

### [Optional] Other Teams Impacted
- None identified.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
The Orcheo workflow receives WeCom webhook requests, validates/decrypts the payload, and sends a fixed reply to the sender using the WeCom message delivery API.

### Technical Requirements
- WeCom callback verification and decryption using `msg_signature`, `timestamp`, `nonce`, plus `Token` and `EncodingAESKey` configured in the WeCom app.
- Access token retrieval and caching using corp ID + corp secret; refresh before message send.
- Secrets sourced from Orcheo vault: `WECOM_CORP_ID`, `WECOM_CORP_SECRET`, `WECOM_TOKEN`, `WECOM_ENCODING_AES_KEY`, `WECOM_AGENT_ID`.
- Observability hooks to log validation failures and message delivery status.
- Support local development via HTTPS reverse proxy (for example, Cloudflare Tunnel) to satisfy WeCom callback requirements.

### AI/ML Considerations (if applicable)
Not applicable.

## MARKET DEFINITION (for products or large features)
Not applicable; this is an internal workflow.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] Direct-message reply success | 95%+ reply success in staging over 50 test messages |
| [Secondary] Validation correctness | 0 accepted requests with invalid signatures |

### Rollout Strategy
Start with a staging WeCom app, validate direct-message replies, then enable the workflow in production.

### Experiment Plan (if applicable)
Not applicable.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Staging app | Validate callbacks, replies, and access token handling |
| **Phase 2** | Production app | Enable direct-message responses and monitor delivery metrics |

## HYPOTHESIS & RISKS
- **Hypothesis:** A minimal WeCom responder workflow can provide reliable direct-message replies and serve as a base for future expansions.
- **Risk:** WeCom callback verification or decryption mistakes could reject valid events.
  - **Mitigation:** Validate against official test callbacks and log failures for debugging.
- **Risk:** Access token refresh failures may block message delivery.
  - **Mitigation:** Cache tokens, log refresh errors, and alert when refresh fails.

## APPENDIX
### Sample Message Format
```
Thanks! Your message was received.
```
