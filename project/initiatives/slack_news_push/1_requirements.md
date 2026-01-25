# Requirements Document: Slack News Push

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** Slack News Push Workflow
- **Type:** Feature
- **Summary:** Deliver a scheduled and on-demand Slack digest of unread RSS feed items stored in MongoDB, and mark them as read after posting.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2025-12-20

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Workflow Export | [Slack news push.json](Slack%20news%20push.json) | Shaojie Jiang | n8n Export |
| Design | [design.md](design.md) | Shaojie Jiang | Slack News Push Design |

## PROBLEM DEFINITION
### Objectives
Provide a Slack digest of unread RSS items on a daily schedule and when the bot is mentioned in Slack. Ensure posted items are marked as read while surfacing how many unread items remain beyond the posted batch.

### Target users
Members of the Slack channel receiving the AI/news digest, and operators who maintain the RSS ingestion pipeline.

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Channel member | Receive a daily digest of unread news items | I can review updates without polling the database or RSS feeds | P0 | A message posts at 09:00 with up to 30 unread items and a remaining unread count |
| Channel member | Mention the bot to trigger a digest on demand | I can pull the latest updates when needed | P0 | An app mention in the configured channel triggers the same digest flow |
| Operator | Ensure items that were posted are marked as read | I avoid duplicate posts in subsequent digests | P0 | Documents returned in the digest are updated with `read = true` |

### Context, Problems, Opportunities
The workflow currently lives in n8n, combining a schedule trigger, Slack app-mention trigger, MongoDB queries, formatting logic, Slack delivery, and read-state updates. We need an Orcheo-native version to consolidate workflow governance while keeping the same behavior and output formatting.

### Product goals and Non-goals
**Goals:** Parity with the existing n8n workflow, reliable Slack delivery, consistent formatting, and correct read-state updates across both scheduled and on-demand runs.

**Non-goals:** RSS ingestion, Slack channel administration, or any UI for editing feed items.

## PRODUCT DEFINITION
### Requirements
**P0 (must have)**
- Scheduled trigger runs at 09:00 daily in Europe/Amsterdam (DST enabled) and emits the same payload as the Slack trigger.
- Slack app-mention handling uses a webhook trigger plus a Slack event parser/validator node, scoped to the configured channel.
- Query MongoDB `rss_feeds` collection to count unread items (`read = false`).
- Query MongoDB `rss_feeds` for the most recent unread items, sorted by `isoDate` desc, limited to 30.
- Format the Slack message by decoding HTML entities in titles, replacing `<`/`>` with `[`/`]`, and rendering each item as a Slack link.
- Append `Unread count: <remaining>` where `remaining = total_unread - returned_items`.
- Post the formatted message to the configured channel with `mrkdwn` enabled and no workflow link.
- Update all returned item IDs to `read = true` only after a successful Slack post.
- Continue the workflow when MongoDB queries fail, returning an empty digest and skipping updates while recording errors for observability.

**P1 (nice to have)**
- Configurable item limit and message header/prefix.
- Optional guard to skip posting if there are zero unread items.
- Expose a dry-run mode for operators (format only, no Slack post or DB update).

### Designs (if applicable)
See [design.md](design.md) for the Orcheo workflow design.

### [Optional] Other Teams Impacted
- None identified.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
The Orcheo workflow uses a schedule trigger and a Slack event trigger that both feed into MongoDB read operations, a formatting node, a Slack delivery node, and a MongoDB update step to mark items as read.

### Technical Requirements
- Slack event verification (signing secret, timestamp validation) and channel filtering for `app_mention` events.
- MongoDB operations should extend the existing `MongoDBNode` with structured, operation-specific inputs (pipeline, filter, update, sort, limit, options), plus wrapper nodes for aggregate/find/update operations.
- Secrets sourced from Orcheo vault: `MDB_CONNECTION_STRING`, `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID`, and optional channel allowlists.
- Observability hooks to log query errors and message delivery status.

### AI/ML Considerations (if applicable)
Not applicable.

## MARKET DEFINITION (for products or large features)
Not applicable; this is an internal workflow.

## LAUNCH/ROLLOUT PLAN
### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] Scheduled digest delivery | 7/7 daily messages succeed for a week in staging before production enablement |
| [Secondary] On-demand digest latency | < 10 seconds from Slack mention to message post |
| [Guardrail] Read update accuracy | 100% of posted item IDs are marked read in MongoDB |

### Rollout Strategy
Start with manual Slack mentions and a short schedule (every 5 minutes) in a staging channel, validate output formatting and read updates, then change the schedule to daily at 09:00.

### Experiment Plan (if applicable)
Not applicable.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Staging channel | Validate Slack events, message formatting, and MongoDB updates using on-demand runs |
| **Phase 2** | Production channel | Enable scheduled runs and monitor delivery metrics |

## HYPOTHESIS & RISKS
- **Hypothesis:** A single Orcheo workflow can replace the n8n automation without regressions in Slack message quality or delivery timing; confidence is high due to the direct one-to-one mapping of nodes.
- **Risk:** Slack event verification or channel filtering mistakes could trigger unwanted runs or reject valid events.
  - **Mitigation:** Use signature validation tests and restrict events to the known channel ID.
- **Risk:** MongoDB query failures may lead to empty or partial digests.
  - **Mitigation:** Add error logging and alerting, and ensure failures do not mark items as read.

## APPENDIX
### Sample Message Format
```
* <https://example.com|Example Title>
* <https://example.com|Another Title>
Unread count: 12
```

Note: The original workflow uses a bullet marker equivalent to the Unicode bullet (U+2022). Use the same marker if exact parity is required.
