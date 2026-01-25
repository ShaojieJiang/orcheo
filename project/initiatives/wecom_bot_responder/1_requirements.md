# Requirements Document: WeCom Bot Responder

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** WeCom Bot Responder Workflow
- **Type:** Feature
- **Summary:** Respond to WeCom direct messages and push a scheduled group news digest via Orcheo workflows.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-28

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| WeCom App Setup | https://open.work.weixin.qq.com/wwopen/manual/detail?t=selfBuildApp | WeCom | Official Docs |
| WeCom Message Push | https://developer.work.weixin.qq.com/document/path/99110 | WeCom | Message Push Configuration |
| WeCom AI Bot API Overview | https://developer.work.weixin.qq.com/document/path/101039 | WeCom | AI Bot API Setup |
| WeCom AI Bot Message Push | https://developer.work.weixin.qq.com/document/path/100719 | WeCom | AI Bot Message Formats |
| WeCom AI Bot Passive Reply | https://developer.work.weixin.qq.com/document/path/101031 | WeCom | AI Bot Reply Payloads |
| WeCom AI Bot Active Reply | https://developer.work.weixin.qq.com/document/path/101138 | WeCom | AI Bot response_url Reply |
| WeCom AI Bot Verify/Encrypt | https://developer.work.weixin.qq.com/document/path/101033 | WeCom | AI Bot URL Verification |
| Requirements | [1_requirements.md](1_requirements.md) | Shaojie Jiang | WeCom Bot Responder Requirements |
| Design | [2_design.md](2_design.md) | Shaojie Jiang | WeCom Bot Responder Design |
| Plan | [3_plan.md](3_plan.md) | Shaojie Jiang | WeCom Bot Responder Plan |

## PROBLEM DEFINITION
### Objectives
Deliver a WeCom bot that responds to direct messages with a fixed message and sends a scheduled group news digest. The flow must validate WeCom callbacks, decrypt payloads, and reply to the sender reliably. The news push must post the latest 20 items to a WeCom group every day at 09:00 Amsterdam time.

Add WeCom AI bot support: verify callback URLs, decrypt AI bot callback payloads, and reply to new user messages (passive or active reply).

### Target users
WeCom users who message the app directly and operators who manage the WeCom app and webhook configuration.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| WeCom user | Receive a reply when I message the app | I know the bot is reachable and responsive | P0 | A direct message receives the configured fixed reply |
| Operator | Verify WeCom callbacks are validated and decrypted | I can trust the workflow is secure and stable | P0 | Invalid signatures are rejected and valid callbacks proceed |
| Operator | Receive a daily news digest in a WeCom group | I can share the latest news without manual posting | P1 | A WeCom group receives the latest 20 items at 09:00 Amsterdam time |

### Context, Problems, Opportunities
The previous "news push" workflow is not feasible. Instead, we need a minimal, reliable WeCom bot responder that proves end-to-end webhook handling and messaging, plus a dedicated group message push flow via WeCom Message Push webhooks.

### Product goals and Non-goals
**Goals:** Direct-message response, reliable WeCom callback validation/decryption, a configurable fixed reply message, and a daily group news push via WeCom Message Push.

**Non-goals:** RSS ingestion or complex personalization beyond a fixed reply and a simple news digest format.

## PRODUCT DEFINITION
### Requirements
**P0 (must have)**
- WeCom webhook handling uses a webhook trigger plus a WeCom event parser/validator node.
- Webhook handler supports the WeCom URL verification handshake (GET with `echostr`) and message decryption for encrypted callbacks.
- Only direct messages are processed; group chat messages are ignored.
- Send a fixed response message back to the direct-message sender using WeCom app credentials.
- Return immediate responses for WeCom verification and synchronous checks.
- Respect WeCom platform constraints: HTTPS callback URL, trusted IP allowlist, and access token refresh via corp ID/secret.
- Support WeCom AI bot URL verification and encrypted callbacks (JSON payloads with `encrypt`).
- Support WeCom AI bot message handling for supported message types (text, image, mixed, voice, file, quote) and return replies.
- Support AI bot active replies via `response_url` (single-use URL, 1-hour validity).

**P1 (nice to have)**
- Configurable message type (`text` or `markdown`).
- Optional allowlist of user IDs.
- Scheduled WeCom group news push using Message Push webhook (text or markdown digest).
- Digest includes the latest 20 news items and does not track unread state.
- Passive AI bot replies (encrypted immediate response) for welcome text or direct replies.

### Designs (if applicable)
See [2_design.md](2_design.md) for the Orcheo workflow design.

### [Optional] Other Teams Impacted
- None identified.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
The Orcheo workflow receives WeCom webhook requests, validates/decrypts the payload, and sends a fixed reply to the sender using the WeCom message delivery API. A separate scheduled workflow posts the latest 20 news items to a WeCom group using the Message Push webhook.

### Technical Requirements
- WeCom callback verification and decryption using `msg_signature`, `timestamp`, `nonce`, plus `Token` and `EncodingAESKey` configured in the WeCom app.
- Access token retrieval and caching using corp ID + corp secret; refresh before message send.
- Secrets sourced from Orcheo vault: `WECOM_CORP_ID`, `WECOM_CORP_SECRET`, `WECOM_TOKEN`, `WECOM_ENCODING_AES_KEY`, `WECOM_AGENT_ID`.
- AI bot callback verification and decryption using `msg_signature`, `timestamp`, `nonce`, plus AI bot `Token` and `EncodingAESKey` (ReceiveId is empty for internal AI bots).
- AI bot replies must support encrypted passive reply payloads and active reply POSTs to `response_url`.
- WeCom Message Push webhook key stored in Orcheo vault; keep the webhook URL private and rotate if exposed.
- Message Push supports `text`, `markdown`, `markdown_v2`, `news`, `file`, `image`, `voice`, `template_card` message types; ensure payloads follow WeCom limits (text 2048 bytes, markdown 4096 bytes).
- Message Push rate limit: no more than 20 messages per minute per webhook.
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
| [Secondary] Scheduled digest delivery | 95%+ successful daily pushes over 2 weeks |

### Rollout Strategy
Start with a staging WeCom app, validate direct-message replies, validate Message Push webhook delivery, then enable the workflows in production.

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
