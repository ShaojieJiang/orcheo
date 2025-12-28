# WeCom Bot Responder Workflow

This workflow replies to direct messages sent to a WeCom app with a fixed response.

WeCom callbacks trigger the workflow, which validates the signature, decrypts the
payload, and sends a reply to the user who initiated the message.

## Configuration

### Workflow Configuration

Edit `workflow_config.json` to set:

```json
{
  "configurable": {
    "corp_id": "YOUR_WECOM_CORP_ID",
    "agent_id": 1000002,
    "reply_message": "Thanks! Your message was received.",
    "msg_type": "text",
    "allowlist_user_ids": []
  }
}
```

| Field | Description |
|-------|-------------|
| `corp_id` | WeCom corporation ID |
| `agent_id` | WeCom app agent ID (integer) |
| `reply_message` | Fixed response content to send back to the user |
| `msg_type` | `text` or `markdown` reply type |
| `allowlist_user_ids` | Optional list of user IDs allowed to receive replies |

### Orcheo Vault Secrets

Configure these secrets in the Orcheo vault (referenced via `[[key]]` syntax):

| Secret Key | Description |
|------------|-------------|
| `wecom_corp_secret` | WeCom app secret for access token retrieval |
| `wecom_token` | Callback token for signature validation |
| `wecom_encoding_aes_key` | AES key for callback payload decryption |

## WeCom App Setup

1. Create a self-built app in WeCom admin console
2. Configure the callback URL to point to:
   ```
   https://your-domain/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true
   ```
3. Set the callback Token and EncodingAESKey, then save them in Orcheo vault
4. Enable trusted IPs if required

## Trigger Behavior

### Direct Messages

When a user sends a direct message to the WeCom app:

1. WeCom sends a callback to the webhook endpoint
2. The workflow validates the signature and decrypts the payload
3. The workflow sends the fixed reply to the user

Group chat messages are ignored.

## Message Types

The workflow supports two message types via the `msg_type` field:

- `text` (default): Plain text message
- `markdown`: Markdown-formatted message (WeCom markdown subset)

## Testing

To test the workflow locally:

1. Set up a reverse proxy (e.g., Cloudflare Tunnel) to expose your local server
2. Configure the WeCom callback URL to point to the tunnel
3. Start the Orcheo server with `make dev-server`
4. Send a direct message to the app and confirm the reply
