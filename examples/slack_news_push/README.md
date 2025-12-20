# Slack News Push Workflow Example

This example mirrors the Slack news push workflow using Orcheo nodes, including
Slack Events API handling, MongoDB queries, formatting, Slack posting, and read
updates.

## Prerequisites

Create the required credentials in the Orcheo vault:

- `slack_bot_token` (Slack bot token)
- `slack_team_id` (Slack workspace ID)
- `slack_signing_secret` (Slack Events API signing secret)
- `mdb_connection_string` (MongoDB connection string)

Update the constants in `workflow.py` to match your environment:

- `CHANNEL_ID`
- `DATABASE`
- `COLLECTION`

## Trigger Configuration

Webhook trigger configuration (Slack Events API):

```json
{
  "allowed_methods": ["POST"],
  "required_headers": {},
  "required_query_params": {}
}
```

Cron trigger configuration:

- Staging schedule (every 5 minutes): `*/5 * * * *`
- Production schedule (daily 09:00 Europe/Amsterdam): `0 9 * * *`

## Notes

- The Slack signature is verified inside `SlackEventsParserNode` using the raw
  webhook body; ensure Slack sends its events to
  `/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true`.
- Read updates only occur after Slack reports a successful post.
