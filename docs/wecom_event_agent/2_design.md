# Design Document

## For WeCom Event Agent Workflow

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-01-02
- **Status:** Draft

---

## Overview

The WeCom Event Agent extends the WeCom bot responder patterns to support event
operations through Customer Service messages and internal WeCom direct messages.
It validates and decrypts WeCom callbacks, syncs the latest CS message when
needed, uses an AI agent to parse event intents, stores events and RSVPs in
MongoDB, and replies to the user via Customer Service or internal messaging.

Key goals: reliable WeCom callback handling, structured event/RSVP persistence,
and clear chat responses for create/update and reporting workflows.

## Components

- **Webhook + Parser (WeCom)**
  - `WebhookTriggerNode` for WeCom callbacks.
  - `WeComEventsParserNode` for signature validation, decryption, and CS event
    detection (shared with the WeCom bot responder).
- **Customer Service Sync + Reply**
  - `WeComAccessTokenNode` to fetch access tokens.
  - `WeComCustomerServiceSyncNode` to fetch the latest external message.
  - `WeComCustomerServiceSendNode` to send the reply.
- **Internal Message Reply**
  - `WeComSendMessageNode` to respond to internal WeCom direct messages.
- **Command Parsing**
  - `AgentNode` with a strict JSON schema prompt to classify actions and extract
    event/RSVP fields.
  - `ParseCommandNode` to validate JSON output and normalize action fields.
- **Persistence Layer**
  - `MongoDBNode` for event upserts (by `event_id`).
  - `MongoDBNode` for RSVP upserts (by `event_id` + `attendee_id`).
  - `MongoDBFindNode` to retrieve RSVP lists.
  - `MongoDBFindNode` to retrieve recent events for listing.
- **Response Formatting**
  - Task nodes to format confirmation messages and RSVP lists.
- **Observability**
  - Node-level logging and error handling from core WeCom/MongoDB nodes.

## Request Flows

### Flow 1: Update Event

1. WeCom sends a CS or internal message callback.
2. `WeComEventsParserNode` validates and decrypts the callback.
3. For CS messages, `WeComCustomerServiceSyncNode` fetches the latest CS text message.
4. `AgentNode` parses the message into a JSON command.
5. `PrepareEventUpdateNode` validates required fields and assigns a new event ID
   if missing.
6. `MongoDBNode` upserts the event record.
7. Reply is sent via `WeComCustomerServiceSendNode` or `WeComSendMessageNode`.

### Flow 2: Update RSVP

1. WeCom CS or internal callback triggers the workflow.
2. The latest CS message is synced and parsed into a command.
3. `PrepareRsvpUpdateNode` validates event ID, attendee ID, and status.
4. `MongoDBNode` upserts the RSVP record with updated timestamps.
5. Reply is sent via `WeComCustomerServiceSendNode` or `WeComSendMessageNode`.

### Flow 3: Get Event RSVPs

1. WeCom CS or internal callback triggers the workflow.
2. The latest CS message is parsed into a `get_rsvps` command.
3. `MongoDBFindNode` fetches RSVPs for the event.
4. Reply is sent via `WeComCustomerServiceSendNode` or `WeComSendMessageNode`.

### Flow 4: List Events

1. WeCom CS or internal callback triggers the workflow.
2. The latest message is parsed into a `list_events` command.
3. `MongoDBFindNode` fetches recent events sorted by date.
4. Reply is sent via `WeComCustomerServiceSendNode` or `WeComSendMessageNode`.

## API Contracts

### WeCom Customer Service Callback
```
POST /api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true
Headers:
  Content-Type: text/xml
Query:
  msg_signature, timestamp, nonce
Body:
  <xml>
    <ToUserName><![CDATA[corp_id]]></ToUserName>
    <Encrypt><![CDATA[encrypted_payload]]></Encrypt>
  </xml>
Response:
  200 OK -> success
```

### WeCom Customer Service Send
```
POST https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg?access_token=ACCESS_TOKEN
Body:
  {
    "touser": "EXTERNAL_USER_ID",
    "open_kfid": "OPEN_KF_ID",
    "msgtype": "text",
    "text": {"content": "Event saved: ..."}
  }
Response:
  200 OK -> { "errcode": 0, "errmsg": "ok" }
```

## Data Models / Schemas

### Event Document (MongoDB)
| Field | Type | Description |
|-------|------|-------------|
| event_id | string | Workflow-generated or user-provided ID |
| title | string | Event title |
| description | string | Event description |
| iso_date | string | ISO 8601 date/time |
| location | string | Location text |
| host | object | Host metadata (name/id/email) |
| created_at | string | ISO timestamp |
| updated_at | string | ISO timestamp |

### RSVP Document (MongoDB)
| Field | Type | Description |
|-------|------|-------------|
| event_id | string | Event ID |
| attendee_id | string | WeCom external user ID |
| attendee_name | string | Optional name |
| status | string | yes/no/maybe/cancelled |
| created_at | string | ISO timestamp |
| updated_at | string | ISO timestamp |

## Security Considerations

- Validate WeCom signatures and timestamps to prevent spoofed callbacks.
- Decrypt callbacks with the configured Token and EncodingAESKey.
- Store secrets in Orcheo vault and avoid logging raw secrets.
- Restrict processing to CS events and validate required fields before writes.

## Performance Considerations

- MongoDB upserts avoid separate read-modify-write cycles.
- RSVP list queries use a limit and sort by `updated_at` for predictable output.

## Testing Strategy

- **Unit tests**: command parsing, required field validation, RSVP status mapping.
- **Integration tests**: MongoDB upsert and RSVP fetch behavior.
- **Manual QA checklist**: send CS messages for each command and verify replies.

## Rollout Plan

1. Phase 1: Deploy to a staging WeCom app and validate callback handling.
2. Phase 2: Enable in production and monitor MongoDB writes and reply delivery.

## Open Issues

- Message phrasing is flexible because the agent parses natural language.
- Internal WeCom messages are handled with the same command parsing flow as CS.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-01-02 | Codex | Initial draft |
