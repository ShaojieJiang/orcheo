# Credential Templates

Orcheo ships a governed credential template system providing consistent
configuration across the vault, API, and canvas. Templates encode validation
rules, rotation policies, and governance alerts to keep automations healthy.

## Available Templates

- **Slack Bot Token** – Enforces `xoxb-` token prefix, webhook signing secret,
  and 60-day rotation reminders.
- **OpenAI API Key** – Validates `sk-` key format, optional organisation id, and
  token expiry alerts.
- **PostgreSQL Connection** – Ensures DSN formatting and monitors rotation
  intervals for long-lived connections.

Templates can be queried via `GET /api/credential-templates` and materialised
with `POST /api/credential-templates/{slug}`. Governance alerts surface through
`GET /api/workflows/{id}/credential-governance` prior to trigger execution.
