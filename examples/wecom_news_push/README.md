# WeCom News Push Workflow

This workflow sends scripted messages to a WeCom group chat via two trigger mechanisms:

1. **Scheduled trigger**: Sends messages on a cron schedule (once per minute by default)
2. **App mention trigger**: Responds when the WeCom app is mentioned in a group chat

## Configuration

### Workflow Configuration

Edit `workflow_config.json` to set:

```json
{
  "configurable": {
    "corp_id": "YOUR_WECOM_CORP_ID",
    "chat_id": "YOUR_WECOM_CHAT_ID",
    "agent_id": 1000002,
    "message_template": "Your scripted message content here"
  }
}
```

| Field | Description |
|-------|-------------|
| `corp_id` | WeCom corporation ID |
| `chat_id` | WeCom group chat ID where messages will be sent |
| `agent_id` | WeCom app agent ID (integer) |
| `message_template` | The scripted message content to send |

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
4. Add the app to the target group chat
5. Enable trusted IPs if required

## Trigger Behavior

### Scheduled Messages

The cron trigger is configured to run once per minute (`* * * * *`). To change the schedule, modify the `expression` parameter in the `CronTriggerNode` in `workflow.py`.

Examples:
- `0 9 * * *` - Daily at 09:00
- `*/5 * * * *` - Every 5 minutes
- `0 */2 * * *` - Every 2 hours

### App Mention Messages

When the WeCom app is mentioned in the configured group chat:

1. WeCom sends a callback to the webhook endpoint
2. The workflow validates the signature and decrypts the payload
3. If the message is from the configured chat, it sends the scripted reply

## Message Types

The workflow supports two message types via the `msg_type` field:

- `text` (default): Plain text message
- `markdown`: Markdown-formatted message (WeCom markdown subset)

## Testing

To test the workflow locally:

1. Set up a reverse proxy (e.g., Cloudflare Tunnel) to expose your local server
2. Configure the WeCom callback URL to point to the tunnel
3. Start the Orcheo server with `make dev-server`
4. Mention the app in the WeCom group chat or wait for the scheduled trigger
