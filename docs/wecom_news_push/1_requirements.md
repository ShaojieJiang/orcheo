# Requirements Document: WeCom News Push

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** WeCom News Push Workflow
- **Type:** Feature
- **Summary:** Deliver a scheduled and on-demand WeCom digest of unread RSS feed items stored in MongoDB, and mark them as read after posting.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-28

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| WeCom App Setup | https://open.work.weixin.qq.com/wwopen/manual/detail?t=selfBuildApp | WeCom | Official Docs |
| Requirements | [1_requirements.md](1_requirements.md) | Shaojie Jiang | WeCom News Push Requirements |
| Design | [2_design.md](2_design.md) | Shaojie Jiang | WeCom News Push Design |
| Plan | [3_plan.md](3_plan.md) | Shaojie Jiang | WeCom News Push Plan |

## PROBLEM DEFINITION
### Objectives
Provide a WeCom digest of unread RSS items on a daily schedule and when the WeCom app is mentioned. Ensure posted items are marked as read while surfacing how many unread items remain beyond the posted batch.

### Target users
Members of the WeCom group chat receiving the AI/news digest, and operators who maintain the RSS ingestion pipeline.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Group member | Receive a daily digest of unread news items | I can review updates without polling the database or RSS feeds | P0 | A message posts at 09:00 with up to 30 unread items and a remaining unread count |
| Group member | Mention the app to trigger a digest on demand | I can pull the latest updates when needed | P0 | An @mention in the configured group chat triggers the same digest flow |
| Operator | Ensure items that were posted are marked as read | I avoid duplicate posts in subsequent digests | P0 | Documents returned in the digest are updated with `read = true` |

### Context, Problems, Opportunities
The workflow currently exists in Slack; we need an Orcheo-native WeCom version with identical behavior for scheduled and on-demand runs, using WeCom callbacks and message delivery APIs while keeping the same digest logic and read-state updates.

### Product goals and Non-goals
**Goals:** Parity with the Slack digest behavior, reliable WeCom delivery, consistent formatting, and correct read-state updates across both scheduled and on-demand runs.

**Non-goals:** RSS ingestion, WeCom org setup beyond the required app configuration, or any UI for editing feed items.

## PRODUCT DEFINITION
### Requirements
**P0 (must have)**
- Scheduled trigger runs at 09:00 daily in Europe/Amsterdam (DST enabled) and emits the same payload as the WeCom trigger.
- WeCom callback handling uses a webhook trigger plus a WeCom event parser/validator node, scoped to the configured group chat.
- Webhook handler supports the WeCom URL verification handshake (GET with `echostr`) and message decryption for encrypted callbacks.
- Query MongoDB `rss_feeds` collection to count unread items (`read = false`).
- Query MongoDB `rss_feeds` for the most recent unread items, sorted by `isoDate` desc, limited to 30.
- Format the WeCom message by decoding HTML entities in titles, stripping angle brackets in titles, and rendering each item as a Markdown link.
- Append `Unread count: <remaining>` where `remaining = total_unread - returned_items`.
- Post the formatted message to the configured WeCom group chat using the app credentials and `markdown` or `text` message type (Markdown preferred).
- Update all returned item IDs to `read = true` only after a successful WeCom post.
- Continue the workflow when MongoDB queries fail, returning an empty digest and skipping updates while recording errors for observability.
- Respect WeCom platform constraints: HTTPS callback URL, trusted IP allowlist, and access token refresh via corp ID/secret.

**P1 (nice to have)**
- Configurable item limit and message header/prefix.
- Optional guard to skip posting if there are zero unread items.
- Expose a dry-run mode for operators (format only, no WeCom post or DB update).

### Designs (if applicable)
See [2_design.md](2_design.md) for the Orcheo workflow design.

### [Optional] Other Teams Impacted
- None identified.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
The Orcheo workflow uses a schedule trigger and a WeCom webhook trigger that both feed into MongoDB read operations, a formatting node, a WeCom delivery node, and a MongoDB update step to mark items as read.

### Technical Requirements
- WeCom callback verification and decryption using `msg_signature`, `timestamp`, `nonce`, plus `Token` and `EncodingAESKey` configured in the WeCom app.
- Access token retrieval and caching using corp ID + corp secret; refresh before message send.
- Secrets sourced from Orcheo vault: `WECOM_CORP_ID`, `WECOM_CORP_SECRET`, `WECOM_TOKEN`, `WECOM_ENCODING_AES_KEY`, `WECOM_AGENT_ID`, and optional chat ID allowlists.
- Observability hooks to log query errors, WeCom callback validation failures, and message delivery status.
- Support local development via HTTPS reverse proxy (for example, Cloudflare Tunnel) to satisfy WeCom callback requirements.

### AI/ML Considerations (if applicable)
Not applicable.

## MARKET DEFINITION (for products or large features)
Not applicable; this is an internal workflow.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] Scheduled digest delivery | 7/7 daily messages succeed for a week in staging before production enablement |
| [Secondary] On-demand digest latency | < 10 seconds from WeCom mention to message post |
| [Guardrail] Read update accuracy | 100% of posted item IDs are marked read in MongoDB |

### Rollout Strategy
Start with manual WeCom mentions and a short schedule (every 5 minutes) in a staging chat, validate output formatting and read updates, then change the schedule to daily at 09:00.

### Experiment Plan (if applicable)
Not applicable.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Staging chat | Validate WeCom callbacks, message formatting, and MongoDB updates using on-demand runs |
| **Phase 2** | Production chat | Enable scheduled runs and monitor delivery metrics |

## HYPOTHESIS & RISKS
- **Hypothesis:** A single Orcheo workflow can replace the ad-hoc WeCom automation without regressions in digest quality or delivery timing; confidence is high due to the direct mapping of steps.
- **Risk:** WeCom callback verification or decryption mistakes could trigger unwanted runs or reject valid events.
  - **Mitigation:** Use signature validation tests and restrict events to the known chat ID.
- **Risk:** Access token refresh failures may block message delivery.
  - **Mitigation:** Cache tokens, log refresh errors, and alert when refresh fails.
- **Risk:** MongoDB query failures may lead to empty or partial digests.
  - **Mitigation:** Add error logging and alerting, and ensure failures do not mark items as read.

## APPENDIX
### Sample Message Format
```
- <a href="https://example.com">Example Title</a>
- <a href="https://example.com">Another Title</a>
Unread count: 12
```
