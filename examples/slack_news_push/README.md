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

Configure the workflow with environment variables (defaults shown in
`workflow.py`):

- `SLACK_NEWS_CHANNEL_ID`
- `SLACK_NEWS_DATABASE`
- `SLACK_NEWS_COLLECTION`
- `SLACK_NEWS_ITEM_LIMIT`
- `SLACK_NEWS_SIGNATURE_TOLERANCE_SECONDS`

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
- Keep `slack_signing_secret` configured to enforce signature verification; only
  disable it if you fully trust the webhook source.
- Read updates only occur after Slack reports a successful post.
