# WeCom AI Bot Workflow Example

This example responds to WeCom AI bot callbacks using passive or active
replies.

## Prerequisites

Create the required credentials in the Orcheo vault:

- `wecom_aibot_token` (AI bot callback token)
- `wecom_aibot_encoding_aes_key` (AI bot encoding AES key)

## Configuration

Edit `workflow_config.json`:

- `reply_message`: Fixed reply content.
- `reply_msg_type`: `text`, `markdown`, or `template_card`.
- `use_passive_reply`: `true` to return an encrypted immediate response,
  `false` to send an active reply to `response_url`.
- `receive_id`: Optional receive_id for encryption validation (empty for
  internal AI bots).

## Trigger Configuration

Configure the Webhook trigger with `preserve_raw_body=true` so signature
validation can use the original payload.
