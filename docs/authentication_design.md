# Authentication System Design

## Context
The current FastAPI backend exposes every HTTP and WebSocket route without authentication, allowing unauthenticated callers to manage workflows, execute nodes, and fetch secrets. To support production deployments, Orcheo needs a unified authentication layer that protects REST and WebSocket surfaces while preserving non-interactive automation paths and webhook integrations.

## Goals
- Require authenticated identities for all backend operations (HTTP, WebSocket, CLI, SDK).
- Support both interactive users (canvas, dashboard) and non-interactive automation (CLI, CI, service integrations).
- Scope access to workspaces and workflows using claims embedded in tokens.
- Keep chat session exchange and trigger endpoints secure without leaking long-lived secrets.
- Provide operational controls for rotation, revocation, and observability.

## Architecture Overview
1. **Identity Provider (IdP) integration** – Adopt an OAuth 2.0/OIDC Authorization Code + PKCE flow for first-party clients (canvas, dashboard). The IdP issues short-lived bearer tokens containing subject, workspace, and role claims.
2. **FastAPI authentication dependency** – Introduce a reusable dependency that validates bearer tokens on every HTTP route and WebSocket connection. The dependency should:
   - Verify token signatures (JWKS or introspection).
   - Enforce expiration and audience checks.
   - Extract workspace/workflow scopes and attach them to the request context.
3. **Service tokens for automation** – Implement personal access tokens or OAuth client credentials for CLI, CI, and backend-to-backend calls. Tokens are minted via secure admin flows, hashed at rest, and scoped to specific workspaces/permissions.
4. **Session tokens for ChatKit** – Replace direct return of the static ChatKit secret with short-lived backend-minted tokens (JWT or signed blob) that encode workspace, channel, and expiry. Require authenticated service or user tokens to request session issuance.
5. **Webhook authentication** – Continue supporting shared-secret headers while adding optional HMAC signatures compatible with major providers. Enforce verification before accepting payloads and standardize replay detection.
6. **Authorization enforcement** – Implement policy checks that gate workflow CRUD, execution, credential vault access, and trigger management based on claims (roles, workspace IDs, feature flags). Deny requests when scope claims do not match requested resources.
7. **Observability & operations** – Log authentication events, expose metrics (success/failure counts, latency), and integrate with audit trails. Provide rotation/revocation flows for both IdP-backed and service tokens.

## Components & Responsibilities
| Component | Responsibility |
| --- | --- |
| IdP / Auth server | Issue OIDC tokens, maintain user identities, manage client registrations, publish JWKS for verification. |
| Auth dependency (`authenticate_request`) | Validate bearer tokens, cache JWKS, attach `RequestContext` with identity claims. |
| Token service (`ServiceTokenManager`) | Mint, hash, store, and revoke service tokens; generate scoped JWTs for ChatKit; enforce expirations. |
| Authorization layer (`AuthorizationPolicy`) | Map claims to permissions; enforce workspace/workflow scoping for repositories, triggers, and vault APIs. |
| Webhook verifier | Perform shared-secret or HMAC signature checks, replay protection, and rate limiting prior to trigger invocation. |
| Telemetry & audit | Emit structured logs and metrics for authentication attempts, failures, and token lifecycle events. |

## Request Flows
### Interactive client (canvas/dashboard)
1. User signs in via IdP using Authorization Code + PKCE.
2. Client obtains access token (and refresh token if needed).
3. Client includes `Authorization: Bearer <token>` on REST and WebSocket requests.
4. FastAPI dependency validates the token, enforces scope, and processes the request.

### Automation (CLI/CI)
1. Operator creates a service token scoped to workspace(s) via admin API/UI.
2. Token secret is shown once and stored securely by the operator.
3. CLI/CI includes the token in `Authorization: Bearer <token>` headers.
4. Backend validates token via signature or hashed lookup, applies scopes, and serves the request.

### ChatKit session issuance
1. Authenticated caller requests a ChatKit session for a workflow/workspace.
2. Backend verifies caller scopes and issues a short-lived signed session token with embedded workspace/chat metadata.
3. Frontend uses the session token to interact with ChatKit; expiry limits replay risk.

### Webhook trigger
1. External service sends webhook with shared-secret header or signature.
2. Verifier confirms authenticity (constant-time compare/HMAC), checks timestamp/replay protections, and forwards the payload to trigger execution if valid.

## Implementation Phases
1. **Foundation** – Integrate IdP configuration, implement the FastAPI bearer dependency, and gate all routes/WebSockets behind it.
2. **Service tokens** – Build token minting & hashing service, management APIs, and enforcement middleware.
3. **ChatKit hardening** – Introduce session token issuance endpoint requiring authenticated callers; deprecate static secret exposure.
4. **Webhook signatures** – Extend webhook layer with HMAC signature verification and mandatory secret configuration.
5. **Authorization policies** – Implement fine-grained permission checks across repositories, vault, trigger, and execution surfaces.
6. **Operational tooling** – Add rotation, revocation, logging, and metrics; document runbooks and onboarding steps.

## Open Questions
- Which IdP will Orcheo standardize on for the hosted product (Auth0, Okta, custom Keycloak)?
- Do we require multi-tenant isolation in tokens (workspace vs. organization) for early adopters?
- Should ChatKit leverage the same IdP-issued tokens or a dedicated signing key for session minting?
- How will on-prem/self-hosted deployments manage token signing keys and JWKS distribution?

## Next Steps
- Select IdP and register Orcheo clients (canvas, dashboard, CLI).
- Prototype FastAPI dependency with JWKS caching and attach to routers.
- Design token storage schema (hashed secrets, scopes, expiration) and admin workflows.
- Draft migration plan for existing unauthenticated endpoints and communicate rollout to stakeholders.
