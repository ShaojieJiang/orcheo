# ChatKit Integration Plan

Author: Shaojie Jiang. See `docs/chatkit_integration/requirements.md` and `docs/chatkit_integration/design.md` for full context.

## Milestone 0 – Backend foundations ✅ *(complete)*

All backend prerequisites for ChatKit sharing are now in place. The workflow domain
model understands publish metadata, repository layers persist the new state, and the
ChatKit router accepts either workflow JWTs or publish tokens with consistent
rate-limiting and error handling.

1. **Publish metadata**
   - [x] Extended the workflow model with publish state (`is_public`,
     `publish_token_hash`, `published_at`, `published_by`,
     `publish_token_rotated_at`, `require_login`) and helper utilities for token
     lifecycle management (`generate_publish_token`, `hash_publish_token`,
     `mask_publish_token`).
   - [x] Added persistence updates and tests covering publish, rotate, revoke, and
     `require_login` transitions across in-memory and SQLite repositories.
2. **Publish management APIs**
   - [x] Implemented `POST /api/workflows/{id}/publish`, `/publish/rotate`, and
     `/publish/revoke` endpoints with responses that surface current publish
     status and newly generated tokens when applicable.
   - [x] Ensured the payload accepts the `require_login` flag, publish token hashes
     are persisted (token values only emitted once), and audit logging hooks are
     wired in for future observability.
3. **ChatKit endpoint auth**
   - [x] Updated `/api/chatkit` to validate either workflow-scoped JWTs
     (`Authorization: Bearer …`) or publish tokens, enforcing token hashing, JWT
     checks, OAuth session validation when `require_login` is set, and rate
     limiting via the shared middleware.
   - [x] Persist chat transcripts through the existing session store for both auth
     modes and added backend tests (including
     `tests/backend/test_chatkit_authentication.py`) that cover the new helper
     flows.

## Milestone 1 – CLI and MCP publish UX
_Canvas-side publish surfaces remain future work; this milestone delivers the CLI flows plus matching MCP tools so we can unblock external testing and AI-assistant workflows before Canvas parity ships._
- [x] **Publish command**
  - [x] Implement `orcheo workflow publish <workflow_id>` with a `--require-login` option (default off), confirmation prompts, and summary output showing the share URL/token once.
  - [x] Handle errors (missing workflow, permission denied) with actionable hints and non-zero exit codes.
  - [x] Expose the same flow via `orcheo-mcp` (e.g., `workflows.publish`) so Claude/Codex automations receive identical responses, including one-time token display and require-login flag handling.
- [x] **Unpublish / rotate commands**
  - [x] Add `orcheo workflow unpublish <workflow_id>` and `orcheo workflow rotate-token <workflow_id>` that call the corresponding APIs and update local cache/state.
  - [x] Ensure rotated tokens are only displayed once, older tokens are clearly marked invalid for new sessions, and existing chat connections stay active until they complete.
  - [x] Mirror both actions in MCP tools (`workflows.unpublish`, `workflows.rotate_publish_token`) that stream back the same status payloads and error semantics as the CLI.
- [x] **Status surfacing**
  - [x] Update `orcheo workflow list` and `orcheo workflow show` to include publish status (`public/private`, `require_login` flag, last rotated timestamp, share URL if available), and return the same enriched metadata from the MCP `list_workflows`/`show_workflow` tools.
  - [x] Write CLI + MCP regression tests covering each command/tool path and add docs/examples so users (and assistants) can script the flows consistently.

## Milestone 2 – Public chat page ([reference template](https://github.com/openai/openai-chatkit-advanced-samples/tree/main/frontend))
- [x] **Route + bootstrapping**
  - [x] Add `${canvas_base_url}/chat/:workflowId` page; sessions should open automatically once metadata loads (no publish tokens required).
  - [x] Fetch workflow metadata to display the workflow name only (no description).
  - [x] Initialize shared ChatKit widget with public auth mode and optionally prompt for OAuth login before mounting when `require_login=true`.
- [x] **Hardening & UX**
  - [x] Handle unauthorized/expired sessions with friendly error screens and CTA to contact owner.
  - [x] Add basic rate-limit feedback and loading skeletons; CAPTCHA defenses will be tracked as follow-up work.
  - [x] Ensure OAuth sessions use secure HttpOnly cookies and display clear login prompts when required.

## Milestone 3 – Canvas chat bubble
- [ ] **JWT session issuance**
  - [ ] Add `POST /api/workflows/{id}/chatkit/session` to return 5-min JWTs tied to workflow + user.
  - [ ] Cover with unit tests ensuring permission checks.
- [ ] **UI components**
  - [ ] Create floating FAB + modal in `apps/canvas/src` that lazy-loads the ChatKit widget.
  - [ ] Integrate token refresh logic, workflow switch handling, loading/error states.
  - [ ] Add telemetry for open/close events and request failures.
- [ ] **Shared widget refactor**
  - [ ] Move existing ChatKit client logic into a reusable module (`features/chatkit`).
  - [ ] Deduplicate code paths so Canvas modal and public page import the same component.

## Milestone 4 – QA, docs, rollout
- [ ] **Testing matrix**
  - [ ] Expand backend + frontend test suites (unit + integration) covering both auth modes.
  - [ ] Document manual QA checklist referenced in requirements success metrics, including OAuth-required flows and transcript persistence checks.
- [ ] **Docs & enablement**
  - [ ] Update product docs/tutorials explaining how to publish, share links, and use Canvas bubble.
  - [ ] Ship feature flags (`chatkit_canvas_enabled`, `chatkit_publish_enabled`) and rollout plan.
  - [ ] Monitor logs/metrics post-deploy and prepare rollback steps.
