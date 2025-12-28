# Design Document

## For WeCom News Push Workflow

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-28
- **Status:** Approved

---

## Overview

This workflow delivers a WeCom digest of unread RSS feed items stored in MongoDB. It is triggered either on a daily schedule or when the WeCom app is mentioned in a group chat, and it posts a formatted message containing the latest unread items along with a remaining unread count.

The design mirrors the Slack workflow while mapping steps onto WeCom-specific triggers and message delivery APIs. The flow consists of two trigger entry points that converge on shared MongoDB queries, a formatter, WeCom delivery, and read-state updates. WeCom callbacks are verified and decrypted before use, and message delivery uses app credentials with cached access tokens.

Key goals: parity with the Slack digest behavior, safe WeCom delivery, accurate read updates, and clear observability on query or delivery failures.

## Components

- **Trigger Layer (Orcheo Triggers)**
  - **CronTriggerNode** for the daily 09:00 run (Europe/Amsterdam, DST enabled).
  - **WebhookTriggerNode** for WeCom callback requests.
  - **WeComEventsParserNode (new)** to validate signatures, decrypt payloads, handle URL verification, and filter group messages that mention the app.
- **Trigger Routing Node**
  - **DetectTriggerNode (new)** to detect webhook payloads and route between scheduled vs. WeCom-initiated paths.
- **MongoDB Operations (extend existing node + wrappers)**
  - **MongoDBNode (extended)** adds operation-specific inputs (`filter`, `update`, `pipeline`, `sort`, `limit`, `options`) with validation per operation.
  - **MongoDBAggregateNode** wrapper for the unread count pipeline.
  - **MongoDBFindNode** wrapper for unread item fetch with sort/limit.
- **Formatter Node**
  - **FormatWeComDigestNode (new)** to decode titles, format WeCom Markdown links, compute remaining count, and return `{ news, ids }`.
- **WeCom Delivery**
  - **WeComAccessTokenNode (new)** to fetch/cache access tokens using corp ID + corp secret.
  - **WeComSendMessageNode (new)** to send `markdown` or `text` messages to the target chat or recipients.
- **Read-State Update**
  - **MongoDBUpdateManyNode** wrapper to set `read = true` for the IDs returned in the digest.
- **Observability**
  - Structured logging in the formatter and Mongo nodes to capture query failures and message delivery status.

## Request Flows

### Flow 1: Scheduled Digest

1. `CronTriggerNode` fires at 09:00 (Europe/Amsterdam, DST enabled).
2. `DetectTriggerNode` identifies the run as scheduled and routes to MongoDB reads.
3. `MongoDBAggregateNode` counts unread items: match `read = false`, then `$count`.
4. `MongoDBFindNode` fetches up to 30 unread items sorted by `isoDate` desc.
5. `FormatWeComDigestNode` formats Markdown links, computes remaining unread count, and outputs `{ news, ids }`.
6. `WeComAccessTokenNode` ensures a valid access token is available.
7. `WeComSendMessageNode` posts `news` to the configured chat or recipients.
8. `MongoDBUpdateManyNode` updates matching `_id` values to `read = true` only after a successful WeCom post.

### Flow 2: WeCom Mention Digest

1. `WebhookTriggerNode` receives the WeCom callback request.
2. `DetectTriggerNode` identifies the run as webhook-triggered.
3. `WeComEventsParserNode` validates the signature, handles URL verification, decrypts payloads, and filters for group messages that mention the app in the configured chat.
4. Steps 3-8 from Flow 1 execute identically.

## API Contracts

### WeCom Callback + Parser
```
GET /api/workflows/{workflow_id}/triggers/webhook?msg_signature=...&timestamp=...&nonce=...&echostr=...
Response:
  200 OK -> <echoed plaintext echostr>

POST /api/workflows/{workflow_id}/triggers/webhook?msg_signature=...&timestamp=...&nonce=...
Headers:
  Content-Type: text/xml
Body:
  <xml>
    <ToUserName><![CDATA[corp_id]]></ToUserName>
    <Encrypt><![CDATA[encrypted_payload]]></Encrypt>
  </xml>
Response:
  200 OK -> success
```

### WeCom Message Delivery
```
POST https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=ACCESS_TOKEN
Body:
  {
    "msgtype": "markdown",
    "agentid": 1000002,
    "chatid": "CHAT_ID",
    "markdown": { "content": "<formatted digest>" }
  }
Response:
  200 OK -> { "errcode": 0, "errmsg": "ok" }
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

### WeCom Callback Payload (decrypted)
| Field | Type | Description |
|-------|------|-------------|
| ToUserName | string | Corp/app identifier |
| FromUserName | string | Sender user ID |
| CreateTime | int | Unix timestamp |
| MsgType | string | Message type (expect `text`) |
| Content | string | Text content |
| MentionedList | list[string] | Mentioned user/app IDs |
| ChatId | string | Group chat identifier |

### Workflow State
| Field | Type | Description |
|-------|------|-------------|
| unread_count | int | Total unread count from aggregate |
| items | list[object] | Unread items fetched from MongoDB |
| news | string | Formatted WeCom message body |
| ids | list[string] | Item IDs to mark as read |

## Security Considerations

- Validate WeCom signatures and timestamps to prevent replay or spoofed events.
- Decrypt callback payloads using the app's `Token` and `EncodingAESKey`.
- Restrict triggers to the configured chat ID(s) and optionally a list of allowed user IDs.
- Store WeCom and MongoDB credentials in Orcheo vault and redact them from logs.
- Configure trusted IPs and HTTPS callback URLs per WeCom requirements.

## Performance Considerations

- MongoDB queries should use indexes on `read` and `isoDate` to keep aggregate and find fast.
- Limit the digest to 30 items to bound message length and DB update size.
- Cache WeCom access tokens to avoid excess refresh calls.
- Ensure read updates run only after WeCom delivery succeeds to avoid marking unread items prematurely.

## Testing Strategy

- **Unit tests**: formatter function (HTML entity decoding, WeCom Markdown link formatting, remaining count math).
- **Integration tests**: WeCom parser node (signature validation + decryption), MongoDB aggregate/find/update nodes against a seeded collection.
- **Manual QA checklist**: trigger via WeCom mention, verify message format, verify items are marked read, verify schedule fires at 09:00.

## Rollout Plan

1. Phase 1: Deploy to staging with WeCom mention handling via webhook + parser and a short schedule (every 5 minutes); verify MongoDB queries, formatting, WeCom delivery, and read updates.
2. Phase 2: Change the schedule to daily at 09:00 (Europe/Amsterdam) and monitor WeCom delivery/DB update metrics.

## Open Issues

- [ ] Confirm the exact WeCom message fields needed to detect app mentions in group chats.
- [x] The WeCom app should reply in the same chat as the mention trigger.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-28 | Codex | Initial draft |
