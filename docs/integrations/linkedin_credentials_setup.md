# LinkedIn Credentials Setup for Orcheo

This guide explains how to provision the vault credentials required by
`LinkedInPostNode` without exposing tokens to AI agents.

## Required vault credentials

`LinkedInPostNode` reads three vault-backed credentials at runtime:

| Credential key | Required | Description |
|---|---|---|
| `linkedin_access_token` | Yes | OAuth 2.0 access token with the necessary LinkedIn API scopes |
| `linkedin_refresh_token` | Yes | Refresh token used to renew the access token |
| `linkedin_id_token` | No | OIDC id token; when present it is used instead of the `/v2/userinfo` endpoint to resolve the posting member's identity |

The node references these as `[[linkedin_access_token]]`, `[[linkedin_refresh_token]]`,
and `[[linkedin_id_token]]` in its field defaults — Orcheo substitutes the vault
values at execution time.

## Required LinkedIn scopes

To use `LinkedInPostNode`, ensure your LinkedIn application and granted member consent
include the scopes required by your posting mode:

- `w_member_social` — required for posting as a person.
- `rw_organization_admin` — required to list approved organization pages via
  `organizationAcls` when posting as an organization without an explicit
  `configurable.organization_urn`.

If you resolve member identity via `/v2/userinfo` (no `linkedin_id_token` provided),
also configure the LinkedIn OpenID Connect product and grant:

- `openid`
- `profile`
- `email`

## Provisioning tokens with the `linkedin-oauth` skill

The recommended way to create and store these credentials is the
**`linkedin-oauth`** skill from
[AI-Colleagues/agent-skills](https://github.com/AI-Colleagues/agent-skills).

The skill handles the full OAuth 2.0 authorization-code flow and **uploads the
resulting tokens directly to the Orcheo credential vault**, so the raw token
values are never passed through or visible to AI agents.

Refer to the skill's README for installation and usage instructions.

## Example workflows

End-to-end workflow examples that use `LinkedInPostNode` are available in the
[AI-Colleagues/orcheo-examples](https://github.com/AI-Colleagues/orcheo-examples)
repository. These cover common scenarios such as posting as a person and posting
on behalf of an organization page.
