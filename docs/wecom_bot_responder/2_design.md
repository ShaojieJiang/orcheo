# Design Document

## For WeCom Bot Responder Workflow

- **Version:** 0.1
- **Author:** Codex
- **Date:** 2025-12-28
- **Status:** Approved

---

## Overview

This workflow responds to WeCom direct messages with a fixed reply and posts a scheduled news digest to a WeCom group. It validates and decrypts WeCom callbacks, acknowledges verification requests, sends a reply to the direct-message sender using WeCom message delivery APIs, and posts a daily digest via the WeCom Message Push webhook.

Key goals: reliable WeCom callback handling, secure validation/decryption, simple and predictable responses, and a daily group digest at 09:00 Amsterdam time.

## Components

- **Trigger Layer (Orcheo Triggers)**
  - **WebhookTriggerNode** for WeCom callback requests.
  - **WeComEventsParserNode** to validate signatures, decrypt payloads, handle URL verification, and filter for direct messages only.
- **Scheduled Digest Trigger**
  - **CronTriggerNode** to run at `0 9 * * *` with timezone `Europe/Amsterdam`.
  - **MongoDBFindNode** to fetch the latest 20 news items (sorted by newest first).
  - **FormatNewsDigestNode** (new) to format the latest items into a WeCom-friendly digest.
- **WeCom Delivery**
  - **WeComAccessTokenNode** to fetch/cache access tokens using corp ID + corp secret.
  - **WeComSendMessageNode** to send `text` or `markdown` replies to the direct-message sender.
  - **WeComGroupPushNode** to post digest messages to the Message Push webhook URL.
- **Observability**
  - Structured logging in the parser and send nodes to capture validation failures and delivery status.

## Request Flow

### Flow: WeCom Direct Message Response

1. `WebhookTriggerNode` receives the WeCom callback request.
2. `WeComEventsParserNode` validates the signature, handles URL verification, decrypts payloads, and filters for direct messages.
3. `WeComAccessTokenNode` ensures a valid access token is available.
4. `WeComSendMessageNode` posts the fixed reply to the sender.

### Flow: Daily WeCom Group News Digest

1. `CronTriggerNode` fires daily at 09:00 Amsterdam time.
2. `MongoDBFindNode` fetches the latest 20 news items (sorted by `isoDate`).
3. `FormatNewsDigestNode` formats a markdown (or text) digest without unread filtering.
4. `WeComGroupPushNode` posts the digest to the WeCom Message Push webhook.

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
    "msgtype": "text",
    "agentid": 1000002,
    "touser": "USER_ID",
    "text": { "content": "Thanks! Your message was received." }
  }
Response:
  200 OK -> { "errcode": 0, "errmsg": "ok" }
```

### WeCom Message Push Webhook
```
POST https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WEBHOOK_KEY
Body:
  {
    "msgtype": "markdown",
    "markdown": { "content": "Daily digest\n- Title 1\n- Title 2" }
  }
Response:
  200 OK -> { "errcode": 0, "errmsg": "ok" }
```

## Data Models / Schemas

### WeCom Callback Payload (decrypted)
| Field | Type | Description |
|-------|------|-------------|
| ToUserName | string | Corp/app identifier |
| FromUserName | string | Sender user ID |
| CreateTime | int | Unix timestamp |
| MsgType | string | Message type (expect `text`) |
| Content | string | Text content |
| ChatId | string | Group chat identifier (absent for direct messages) |

### Workflow State
| Field | Type | Description |
|-------|------|-------------|
| user | string | Direct-message sender ID |
| content | string | Original message content |
| reply_message | string | Configured fixed reply |
| digest | string | Markdown or text digest for group push |

## Security Considerations

- Validate WeCom signatures and timestamps to prevent replay or spoofed events.
- Decrypt callback payloads using the app's `Token` and `EncodingAESKey`.
- Restrict triggers to direct messages and optionally a list of allowed user IDs.
- Store WeCom credentials in Orcheo vault and redact them from logs.
- Configure trusted IPs and HTTPS callback URLs per WeCom requirements.
- Protect the Message Push webhook key; rotate if exposed and keep it out of source control.

## Local Development

- Use an HTTPS reverse proxy (for example, Cloudflare Tunnel) to expose the local
  webhook endpoint to WeCom.
- Keep the proxy URL in sync with WeCom callback settings during testing.

## Performance Considerations

- Cache WeCom access tokens to avoid excess refresh calls.
- Keep response logic minimal to reduce latency.

## Testing Strategy

- **Unit tests**: parser validation and direct-message detection.
- **Integration tests**: WeCom parser node (signature validation + decryption) and send node against a mocked WeCom API.
- **Digest tests**: format node for daily digest and webhook payload serialization.
- **Manual QA checklist**: send a direct message, verify reply, verify URL verification behavior.

## Rollout Plan

1. Phase 1: Deploy to staging with direct-message handling and verify callback/response behavior.
2. Phase 2: Enable the workflow in production and monitor delivery metrics.

## Open Issues

- None.

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-28 | Codex | Initial draft |
