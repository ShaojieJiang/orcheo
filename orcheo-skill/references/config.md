# Configure Orcheo CLI

## Purpose

Configure `orcheo` CLI through the `orcheo config` command so regular `orcheo` commands do not require repeated environment exports.
When needed, use `orcheo config --help` to see all available options.

## Required values

Ask the user for the following values:
- `--api-url` (always required)
- one of:
  - `--service-token`
  - `--auth-issuer` and `--auth-client-id` and `--auth-audience`

## Optional values

Ask if the user needs to provide the following values:
- `--auth-organization`
