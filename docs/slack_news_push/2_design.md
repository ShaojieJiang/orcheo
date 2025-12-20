# Design Document

## For Slack News Push Workflow

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-20
- **Status:** Approved

---

## Overview

This workflow delivers a Slack digest of unread RSS feed items stored in MongoDB. It is triggered either on a daily schedule or when the bot is mentioned in Slack, and it posts a formatted message containing the latest unread items along with a remaining unread count.

The design mirrors the existing n8n workflow while mapping steps onto Orcheo nodes. The flow consists of two trigger entry points that converge on shared MongoDB queries, a formatter, Slack delivery, and read-state updates. MongoDB operations are implemented by extending the existing `MongoDBNode` with typed operation inputs, plus small wrapper nodes for common operations to keep workflows readable.

Key goals: parity with the n8n workflow, safe Slack delivery, accurate read updates, and clear observability on query or delivery failures.

## Components

- **Trigger Layer (Orcheo Triggers)**
  - **CronTriggerNode** for the daily 09:00 run (Europe/Amsterdam, DST enabled).
  - **WebhookTriggerNode** for Slack Events API callbacks.
  - **SlackEventsParserNode (new)** to verify Slack signatures, handle URL verification, and filter `app_mention` events by channel.
- **MongoDB Operations (extend existing node + wrappers)**
  - **MongoDBNode (extended)** adds operation-specific inputs (`filter`, `update`, `pipeline`, `sort`, `limit`, `options`) with validation per operation.
  - **MongoDBAggregateNode** wrapper for the unread count pipeline.
  - **MongoDBFindNode** wrapper for unread item fetch with sort/limit.
- **Formatter Node**
  - **PythonCode** (or **JavaScriptSandboxNode**) to decode titles, format Slack links, compute remaining count, and return `{ news, ids }`.
- **Slack Delivery**
  - **SlackNode** using `slack_post_message` with `mrkdwn` enabled.
- **Read-State Update**
  - **MongoDBUpdateManyNode** wrapper to set `read = true` for the IDs returned in the digest.
- **Observability**
  - Structured logging in the formatter and Mongo nodes to capture query failures and message delivery status.

## Request Flows

### Flow 1: Scheduled Digest

1. `CronTriggerNode` fires at 09:00 (Europe/Amsterdam, DST enabled).
2. `MongoDBAggregateNode` counts unread items: match `read = false`, then `$count`.
3. `MongoDBFindNode` fetches up to 30 unread items sorted by `isoDate` desc.
4. `PythonCode` formats Slack links, computes remaining unread count, and outputs `{ news, ids }`.
5. `SlackNode` posts `news` to the configured channel.
6. `MongoDBUpdateManyNode` updates matching `_id` values to `read = true` only after a successful Slack post.

### Flow 2: Slack Mention Digest

1. `WebhookTriggerNode` receives the Slack Events API callback.
2. `SlackEventsParserNode` validates the signature, handles URL verification, and filters for `app_mention` events in the configured channel.
3. Steps 2-6 from Flow 1 execute identically.

## API Contracts

### Slack Events Webhook + Parser
```
POST /api/workflows/{workflow_id}/triggers/webhook
Headers:
  X-Slack-Signature: v0=...
  X-Slack-Request-Timestamp: <unix timestamp>
Body:
  {
    "type": "event_callback",
    "event": {
      "type": "app_mention",
      "channel": "C0946SY4TTM",
      "text": "@bot latest?",
      "user": "U123"
    }
  }

Response:
  202 Accepted -> { run_id: "...", status: "queued" }
```

### Slack Message Delivery
```
Tool: slack_post_message
Args:
  channel_id: "C0946SY4TTM"
  text: "<formatted digest>"
  mrkdwn: true
Response:
  200 OK -> { ok: true, ts: "...", channel: "..." }
```

## Data Models / Schemas

### MongoDB Document (`rss_feeds`)
| Field | Type | Description |
|-------|------|-------------|
| _id | string | Document identifier |
| title | string | Feed item title (may contain HTML entities) |
| link | string | Source URL |
| isoDate | string | ISO timestamp for sorting |
| read | bool | Read flag |

### Workflow State
| Field | Type | Description |
|-------|------|-------------|
| unread_count | int | Total unread count from aggregate |
| items | list[object] | Unread items fetched from MongoDB |
| news | string | Formatted Slack message body |
| ids | list[string] | Item IDs to mark as read |

## Security Considerations

- Validate Slack signatures and timestamps to prevent replay or spoofed events.
- Restrict Slack triggers to the configured channel ID.
- Store Slack and MongoDB credentials in Orcheo vault and redact them from logs.

## Performance Considerations

- MongoDB queries should use indexes on `read` and `isoDate` to keep aggregate and find fast.
- Limit the digest to 30 items to bound Slack message length and DB update size.
- Ensure read updates run only after Slack delivery succeeds to avoid marking unread items prematurely.

## Testing Strategy

- **Unit tests**: formatting function (HTML entity decoding, Slack link formatting, remaining count math).
- **Integration tests**: MongoDB aggregate/find/update nodes against a seeded collection.
- **Manual QA checklist**: trigger via Slack mention, verify message format, verify items are marked read, verify schedule fires at 09:00.

## Rollout Plan

1. Phase 1: Deploy to staging with Slack mention handling via webhook + parser and a short schedule (every 5 minutes); verify MongoDB queries, formatting, Slack delivery, and read updates.
2. Phase 2: Change the schedule to daily at 09:00 (Europe/Amsterdam) and monitor Slack delivery/DB update metrics.

## Open Issues

- [ ] Define the exact Slack Events parser contract (input/output schema and error handling).

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-20 | Codex | Initial draft |
