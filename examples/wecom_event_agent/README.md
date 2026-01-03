# WeCom Event Agent Workflow Example

This example processes WeCom Customer Service (CS) and internal WeCom messages to:

- Create or update events
- Capture RSVPs (yes/no/maybe/cancelled)
- List RSVPs for an event

The workflow validates WeCom callbacks, syncs the latest CS message, parses the
user request into a structured command, stores data in MongoDB, and replies to
the user via Customer Service.

## Configuration

Edit `workflow_config.json` to set:

```json
{
  "configurable": {
    "corp_id": "YOUR_WECOM_CORP_ID",
    "agent_id": 1000002,
    "events_database": "events",
    "events_collection": "events",
    "rsvps_collection": "event_rsvps"
  }
}
```

| Field | Description |
|-------|-------------|
| `corp_id` | WeCom corporation ID |
| `agent_id` | WeCom app agent ID for internal messages |
| `events_database` | MongoDB database name for events/RSVPs |
| `events_collection` | MongoDB collection for events |
| `rsvps_collection` | MongoDB collection for RSVPs |

## Orcheo Vault Secrets

Configure these secrets in the Orcheo vault (referenced via `[[key]]` syntax):

| Secret Key | Description |
|------------|-------------|
| `wecom_corp_secret` | WeCom app secret for access token retrieval |
| `wecom_token` | Callback token for signature validation |
| `wecom_encoding_aes_key` | AES key for callback payload decryption |
| `mdb_connection_string` | MongoDB connection string |
| `openai_api_key` | API key for the agent model |

## WeCom Customer Service Setup

1. Create a self-built app in the WeCom admin console.
2. Configure the callback URL to point to:
   ```
   https://your-domain/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true
   ```
3. Set the callback Token and EncodingAESKey, then save them in the Orcheo vault.
4. Enable WeChat Customer Service in the app settings and assign the app to the
   Customer Service account.

## Internal WeCom Messages

Internal users can message the app directly. The workflow handles these messages
with the same command parsing and MongoDB updates as CS messages, replying via
the WeCom app using `agent_id`.

## Example Prompts

- "Update event: Team meetup on 2025-03-20 at HQ, hosted by Alex. Agenda: roadmap."
- "RSVP yes for event 4f7a..."
- "Get RSVPs for event 4f7a..."
- "List upcoming events"

## Testing

1. Use an HTTPS tunnel (for example, Cloudflare Tunnel) to expose your local
   server to WeCom.
2. Start the Orcheo server with `make dev-server`.
3. Send a Customer Service message and confirm the workflow reply.
