# ChatKit Integration Design

## Overview
This document describes the system design for integrating ChatKit into Orcheo across two client surfaces (public page, Canvas chat bubble) and a unified backend endpoint. The design targets incremental delivery while minimizing duplicated UI logic.

## Components
- **Canvas Frontend (TypeScript/React)**
  - Adds floating chat bubble, modal container, and shared ChatKit widget.
  - Responsible for requesting JWTs from Canvas backend and passing them to ChatKit client.
- **Public Chat Frontend (Canvas app shell)**
  - Static route served under `${canvas_base_url}/chat/:workflowId`; publish tokens must stay out of the URL surface. Prefer receiving them via the publish flow and keeping them in memory, only falling back to a `?token=` query string when embedding without prior context is impossible.
  - Loads the same ChatKit widget bundle used by Canvas, initializing with publish token auth and read-only workflow metadata (name only).
  - If the workflow was published with `require_login=true`, prompts the visitor to complete OAuth (e.g., Google) before instantiating the widget.
- **CLI Publishing UX (orcheo CLI)**
  - Adds `orcheo workflow publish` / `unpublish` / `rotate-token` commands with interactive prompts and flags (e.g., `--require-login`) plus post-run summaries displaying the shareable URL.
  - Persists the last-published workflow state locally to show status in `orcheo workflow list`.
  - Surfaces errors (e.g., missing permissions, invalid workflow) inline with actionable remediation hints.
  - Canvas-side publish UX parity is explicitly deferred until after the CLI flow ships; the CLI acts as the authoritative entry point for initial rollout.
- **Canvas Backend (FastAPI)**
  - Provides publish/unpublish/token-rotation APIs.
  - Issues workflow-scoped JWTs for authenticated editors.
- **OAuth/Auth Provider**
  - Reuses existing Canvas OAuth clients; issues short-lived session cookies for public visitors when login is required.
- **ChatKit Backend (FastAPI existing)**
  - Single `/api/chatkit` endpoint supporting both auth modes.
  - Orchestrates workflow invocation, handles streaming responses, and enforces rate limits by reusing the shared middleware in `apps/backend/src/orcheo_backend/app/authentication/rate_limit.py`.
- **Persistence**
  - Workflow table gains `is_public`, `publish_token_hash`, `published_at`, `published_by`, `publish_token_rotated_at`, and `require_login`.
  - JWT signing keys stored in secure config (through environment variable `ORCHEO_AUTH_JWT_SECRET`).
  - ChatKit transcripts (public or Canvas) persist via existing session store with default infinite retention unless a future policy sets TTLs.

## Request Flows
### 1. Canvas Chat Bubble (authenticated)
1. User opens workflow in Canvas editor.
2. Clicking chat bubble triggers `/api/workflows/{id}/chatkit/session` call.
3. Backend validates user permissions and issues JWT: `{sub, workflow_id, permissions, exp}`.
4. Modal instantiates ChatKit widget with `authMode = "jwt"` and uses `Authorization: Bearer <token>` on websocket/HTTP.
5. ChatKit backend verifies signature, checks workflow access, executes workflow, streams response.
6. On token expiry (~5 min), frontend refreshes via silent request.

### 2. Public Chat Page (publish token + optional OAuth)
1. Owner publishes workflow, backend generates `publish_token` and exposes URL `.../chat/{workflowId}` (tokens are delivered out-of-band and stored only in memory; fall back to `?token=` links only when there is no alternative).
2. Visitor loads page; Canvas app fetches workflow metadata (name only) with workflowId and determines whether login is required.
3. If `require_login=true` and no session cookie exists, visitor is sent through OAuth (state param ties back to workflowId + token). After OAuth success, session cookie is set.
4. Widget initializes with `authMode = "publish"`, storing token only in JS memory.
5. Each request posts `{workflow_id, publish_token}` plus relies on the OAuth session when required; ChatKit backend hashes token, compares to stored hash, confirms workflow `is_public`, and optionally validates session claims.
6. Rate limiter tracks per `publish_token`, per IP, and per OAuth user (when available).
7. If owner rotates token, old token stops authorizing new sessions immediately while existing chat connections keep streaming until they end or disconnect.

### 3. CLI Publish/Unpublish flow
1. User runs `orcheo workflow publish <workflow_id> [--require-login]`; CLI fetches workflow metadata and either respects the flag or prompts when omitted, then confirms public exposure.
2. CLI invokes `POST /api/workflows/{id}/publish` with selected options and prints the resulting share URL/token once.
3. Subsequent `orcheo workflow rotate-token <workflow_id>` or `orcheo workflow unpublish <workflow_id>` commands hit the rotate/revoke endpoints, updating local cache and printing status.
4. CLI exit codes reflect success/failure so scripts can automate publishing.

## API Contract
```
POST /api/chatkit
Headers:
  Authorization: Bearer <jwt>   # optional
Body fields:
  workflow_id: str
  publish_token: str | null
  messages: ChatMessage[]
  client_id: str (for dedupe)
  oauth_session: bool (implicit via cookie)

Responses:
  200 OK -> stream or JSON
  401 Unauthorized -> missing/invalid token
  403 Forbidden -> workflow unpublished or access denied
  429 Too Many Requests -> rate limit triggered
```

### Session issuance
```
POST /api/workflows/{workflow_id}/chatkit/session
Headers: Cookie auth
Body: {}
Response 200: { token: <jwt>, expires_in: 300 }
```

### Publish management
```
POST   /api/workflows/{id}/publish         -> marks public + generates token + sets require_login flag
POST   /api/workflows/{id}/publish/rotate  -> rotates token
POST   /api/workflows/{id}/publish/revoke  -> unpublish
```

## Frontend Architecture
- Introduce shared ChatKit client module under `apps/canvas/src/features/chatkit/`.
- Modal component reads workflow context, lazy-loads widget bundle to keep editor light.
- Public page imports the same widget but passes `readOnly: true`, publishes mode, and hides editor-specific controls.
- Use React context or Zustand store for chat state; sessions persist via ChatKit backend so the widget only needs in-memory cache for current display.

## Security Considerations
- Publish tokens stored hashed (e.g., SHA-256) to mitigate leakage; token value only displayed once after publish.
- Strict CORS rules on backend to only allow Canvas/public domains.
- JWT secret rotation via env var; default signing key comes from `ORCHEO_AUTH_JWT_SECRET` and should be rotated regularly (kid header for seamless rollover).
- OAuth login flow uses PKCE + state tokens to prevent CSRF; tokens stored in HttpOnly cookies.
- Instrument abuse monitoring: log auth failures (without tokens), emit metrics by publish token/OAuth user/IP, and feed dashboards owned by Platform Admin + SRE on-call; active CAPTCHA or challenge flows remain future work beyond this phase.

## Testing Strategy
- Unit tests for publish/unpublish/token rotation logic (backend + CLI commands).
- Integration tests for `/api/chatkit` verifying both auth paths.
- Frontend tests for modal open/close, token refresh, and URL token handling.
- Manual QA checklist covering:
  - Publish workflow -> share link -> chat works unauthenticated.
  - Publish workflow with login required -> OAuth prompt -> chat works after auth.
  - Unpublish -> public link fails with 403.
  - Canvas modal respects workflow switch and token expiry.
  - Transcript persistence verified by reloading page and pulling session history via backend tools.

## Rollout Plan
1. Implement backend publish metadata + APIs behind flag.
2. Ship Canvas chat bubble + JWT flow gated by `chatkit_canvas_enabled` flag for internal users.
3. Deploy public page but keep publish flag disabled until backend load testing complete.
4. Gradually enable publish feature per tenant and monitor metrics.

## Open Issues
- Determine hosting path for public assets when canvas app is deployed separately.
- Canvas publishing UX should mirror the CLI flows (same prompts/options) as follow-up work once the CLI implementation lands, to keep user expectations aligned.
