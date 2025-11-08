# ChatKit Integration Plan

Author: Shaojie Jiang. See `docs/chatkit_integration/requirements.md` and `docs/chatkit_integration/design.md` for full context.

## Milestone 0 – Backend foundations (highest priority)
1. **Publish metadata**
   - Extend workflow model with `is_public`, `publish_token_hash`, `published_at`, `published_by`, `publish_token_rotated_at`, `require_login`.
   - Add migration + tests covering publish/rotate/revoke/login-flag state transitions.
2. **Publish management APIs**
   - Implement `POST /api/workflows/{id}/publish`, `/publish/rotate`, `/publish/revoke` per design doc.
   - Payload must accept `require_login` flag; responses include current status + newly generated token (shown once).
   - Instrument audit logging and persist publish token hash only.
3. **ChatKit endpoint auth**
   - Update `/api/chatkit` to accept either workflow-scoped JWT (`Authorization: Bearer ...`) or `{publish_token}` (plus OAuth session when required).
   - Enforce token hashing, JWT validation, OAuth session validation, rate limiting (via the existing middleware in `apps/backend/src/orcheo_backend/app/authentication/rate_limit.py`), and consistent error responses.
   - Persist chat transcripts via existing session store for both auth modes.

## Milestone 1 – CLI publish UX
_Canvas-side publish surfaces remain future work; this milestone only delivers the CLI pathways so we can unblock external testing sooner._
1. **Publish command**
   - Implement `orcheo workflow publish <workflow_id>` with a `--require-login` option (default off), confirmation prompts, and summary output showing the share URL/token once.
   - Handle errors (missing workflow, permission denied) with actionable hints and non-zero exit codes.
2. **Unpublish / rotate commands**
   - Add `orcheo workflow unpublish <workflow_id>` and `orcheo workflow rotate-token <workflow_id>` that call the corresponding APIs and update local cache/state.
   - Ensure rotated tokens are only displayed once, older tokens are clearly marked invalid for new sessions, and existing chat connections stay active until they complete.
3. **Status surfacing**
   - Update `orcheo workflow list` and `orcheo workflow show` to include publish status (`public/private`, `require_login` flag, last rotated timestamp, share URL if available).
   - Write CLI tests covering each command path and add docs/examples so users can script the flows.

## Milestone 2 – Canvas chat bubble
1. **JWT session issuance**
   - Add `POST /api/workflows/{id}/chatkit/session` to return 5-min JWTs tied to workflow + user.
   - Cover with unit tests ensuring permission checks.
2. **UI components**
   - Create floating FAB + modal in `apps/canvas/src` that lazy-loads the ChatKit widget.
   - Integrate token refresh logic, workflow switch handling, loading/error states.
   - Add telemetry for open/close events and request failures.
3. **Shared widget refactor**
   - Move existing ChatKit client logic into a reusable module (`features/chatkit`).
   - Deduplicate code paths so Canvas modal and public page import the same component.

## Milestone 3 – Public chat page ([reference template](https://github.com/openai/openai-chatkit-advanced-samples/tree/main/frontend))
1. **Route + bootstrapping**
   - Add `${canvas_base_url}/chat/:workflowId` page; tokens should stay hidden (use in-memory storage from publish response), falling back to a `?token=` query string only if embedding without prior context is impossible.
   - Fetch workflow metadata to display the workflow name only (no description).
   - Initialize shared ChatKit widget with publish-token auth mode and optionally prompt for OAuth login before mounting when `require_login=true`.
2. **Hardening & UX**
   - Handle invalid/expired tokens with friendly error screens and CTA to contact owner.
   - Add basic rate-limit feedback and loading skeletons; CAPTCHA defenses will be tracked as follow-up work.
   - Ensure publish tokens never persist beyond in-memory storage and OAuth sessions use secure HttpOnly cookies.

## Milestone 4 – QA, docs, rollout
1. **Testing matrix**
   - Expand backend + frontend test suites (unit + integration) covering both auth modes.
   - Document manual QA checklist referenced in requirements success metrics, including OAuth-required flows and transcript persistence checks.
2. **Docs & enablement**
   - Update product docs/tutorials explaining how to publish, share links, and use Canvas bubble.
   - Ship feature flags (`chatkit_canvas_enabled`, `chatkit_publish_enabled`) and rollout plan.
   - Monitor logs/metrics post-deploy and prepare rollback steps.
