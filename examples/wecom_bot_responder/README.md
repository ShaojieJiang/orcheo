# WeCom Bot Responder Workflow

This workflow replies to direct messages sent to a WeCom app with a fixed response.
It supports both:

- Internal WeCom users (direct app messages)
- External WeChat users via WeCom Customer Service (微信客服)

WeCom callbacks trigger the workflow, which validates the signature, decrypts the
payload, and sends a reply to the user who initiated the message.

## Configuration

### Workflow Configuration

Edit `workflow_config.json` to set:

```json
{
  "configurable": {
    "agent_id": 1000002,
    "reply_message": "Thanks! Your message was received."
  }
}
```

| Field | Description |
|-------|-------------|
| `agent_id` | WeCom app agent ID (integer) |
| `reply_message` | Fixed response content to send back to the user |

### Orcheo Vault Secrets

Configure these secrets in the Orcheo vault (referenced via `[[key]]` syntax):

| Secret Key | Description |
|------------|-------------|
| `wecom_corp_id` | WeCom corporation ID |
| `wecom_app_secret` | WeCom app secret for access token retrieval |
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
5. If using Customer Service, follow the following steps:
    1. Enable WeChat Customer Service in the WeCom app settings
    2. Create a Customer Service account and make sure "Receptionist" is empty
    3. In "In-house development" section, select the created app for Customer Service messages

## Trigger Behavior

### Direct Messages (Internal Users)

When a user sends a direct message to the WeCom app:

1. WeCom sends a callback to the webhook endpoint
2. The workflow validates the signature and decrypts the payload
3. The workflow sends the fixed reply to the user

Group chat messages are ignored.

### Customer Service Messages (External Users)

When an external WeChat user contacts your Customer Service account:

1. WeCom sends a `kf_msg_or_event` callback to the webhook endpoint
2. The workflow syncs the latest Customer Service messages
3. The workflow replies to the most recent text message from the external user

Non-text Customer Service messages are ignored.

## Message Types

This example uses the default text reply. If you customize the workflow:

- Internal user replies can be `text` or `markdown`
- Customer Service replies are `text` only

## Testing

To test the workflow locally:

1. Set up a reverse proxy (e.g., Cloudflare Tunnel) to expose your local server
2. Configure the WeCom callback URL to point to the tunnel
3. Start the Orcheo server with `make dev-server`
4. Send a direct message (or Customer Service message) and confirm the reply
