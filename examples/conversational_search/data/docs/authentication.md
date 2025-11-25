# Authentication and Access Control

Orcheo Cloud supports multiple authentication methods so teams can secure their workflows without sacrificing developer velocity.

## OAuth2 Client Credentials
- Create an application in the Orcheo console and download the client ID and secret.
- Set the values in your environment as `ORCHEO_CLIENT_ID` and `ORCHEO_CLIENT_SECRET`.
- Tokens are short lived and automatically refreshed by the SDK.

## API Keys
- API keys are scoped to a workspace and can be restricted to specific nodes.
- Keys should be stored in your secret manager; never commit them to source control.
- Rotate keys regularly and audit access logs from the console.

## Single Sign-On
- SSO supports SAML 2.0 and OIDC providers.
- Map identity provider groups to Orcheo roles to control access to deployments.

## Least-Privilege Recommendations
- Grant service tokens only to automation workflows that need them.
- Use environment-based roles (dev, staging, prod) to separate privileges.
- Enable audit logging for all deployment actions and sensitive node executions.
