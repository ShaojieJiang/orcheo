# WeCom News Push Workflow Example

This example sends a daily digest of the latest 20 news items to a WeCom group
using the Message Push webhook.

## Prerequisites

Create the required credentials in the Orcheo vault:

- `wecom_group_webhook_key` (WeCom group webhook key)
- `mdb_connection_string` (MongoDB connection string)

Configure the workflow with environment variables (defaults shown in
`workflow.py`):

- `WECOM_NEWS_DATABASE`
- `WECOM_NEWS_COLLECTION`
- `WECOM_NEWS_MESSAGE_TYPE` (text or markdown)

## Trigger Configuration

Cron trigger configuration:

- Production schedule (daily 09:00 Europe/Amsterdam): `0 9 * * *`

## Notes

- The workflow does not filter unread items; it always pushes the latest 20
  entries based on `isoDate`.
- Use `message_type=markdown` to get link formatting.
