# Milestone 3 Security Review

_Date completed: 2025-10-18_

## Scope & Stakeholders
- **Vault surfaces** – credential lifecycle, encryption, rotation, auditing, and OAuth handling across `BaseCredentialVault` helpers and metadata models. 【F:src/orcheo/vault/__init__.py†L35-L198】【F:src/orcheo/models/workflow.py†L539-L671】
- **Trigger services** – webhook, cron, manual dispatch, retry orchestration, and trigger health guards exercised through the consolidated trigger layer. 【F:src/orcheo/triggers/webhook.py†L1-L205】【F:src/orcheo/triggers/layer.py†L17-L210】
- **Execution/runtime surfaces** – FastAPI repository abstractions, run history persistence, and trigger dispatch paths inside the SQLite development backend. 【F:apps/backend/src/orcheo_backend/app/repository_sqlite.py†L33-L520】【F:apps/backend/src/orcheo_backend/app/history.py†L1-L120】

Stakeholders included the backend lead (repository & runtime), security reviewer, and the trigger/vault component owners to validate remediation ownership and sequencing.

## Methodology
1. **Architecture review** – Cross-referenced the credential vault, trigger layer, and runtime diagrams with the implementation to map trust boundaries (SDK callers, trigger entry points, worker queues) before enumerating threats. 【F:docs/design.md†L20-L164】
2. **Threat modeling** – Identified asset flows (secrets, OAuth refresh tokens, webhook payloads) and abuse cases (secret exfiltration, trigger replay, tenant bleed) and documented mitigations per component.
3. **Targeted penetration tests** – Exercised webhook validation, cron overlap protection, retry throttling, and vault rotation APIs using crafted requests and mocked contexts.
4. **Secure code review** – Audited encryption, logging, and persistence logic for secret exposure, constant-time comparisons, and data isolation.
5. **Remediation & regression tests** – Landed fixes and expanded coverage for sensitive header scrubbing while running full lint/test suites prior to sign-off.

## Threat Modeling Summaries
### Credential Vault
- AES-GCM encryption and OAuth token envelopes ensure secrets at rest are encrypted, and rotation enforces new material while resetting health status for downstream checks. 【F:src/orcheo/vault/__init__.py†L48-L123】【F:src/orcheo/models/workflow.py†L566-L641】
- Scope enforcement relies on workflow/workspace roles; threat model confirmed access context validation denies requests outside configured scopes. 【F:src/orcheo/models/workflow.py†L308-L387】
- Identified need to surface tamper-evident audit event exports for external SIEM integration (tracked as follow-up below).

### Trigger Layer
- Webhook validation now performs constant-time shared-secret comparisons and removes secrets from stored headers, preventing timing leaks and accidental run history exposure. 【F:src/orcheo/triggers/webhook.py†L134-L208】【F:src/orcheo/triggers/layer.py†L123-L153】
- Rate limiting and retry backoff logic mitigate brute-force and replay attempts; cron overlap guards prevent concurrent reentry. 【F:src/orcheo/triggers/webhook.py†L172-L204】【F:src/orcheo/triggers/cron.py†L105-L205】【F:src/orcheo/triggers/retry.py†L23-L185】
- Manual dispatch validation sanitizes actor inputs and version targeting, closing privilege-escalation vectors through batch operations. 【F:src/orcheo/triggers/manual.py†L20-L158】

### Execution & Runtime Surfaces
- Repository operations gate trigger dispatch on credential health via the trigger layer guard, ensuring unhealthy credentials block execution. 【F:apps/backend/src/orcheo_backend/app/repository_sqlite.py†L471-L520】
- Run history store confines payload mutations under an async lock, preventing concurrent writes from leaking cross-run data. 【F:apps/backend/src/orcheo_backend/app/history.py†L49-L120】
- Threat model highlighted the absence of tenant-aware sandboxing in the LangGraph execution worker—captured as a follow-up for Milestone 6 hardening.

## Findings & Resolutions
| ID | Severity | Finding | Resolution | Owner |
| --- | --- | --- | --- | --- |
| SR-001 | High | Webhook shared-secret validation used direct equality comparison, enabling timing attacks. | Switched to `hmac.compare_digest` for constant-time comparison and added regression tests. 【F:src/orcheo/triggers/webhook.py†L19-L200】【F:tests/test_triggers_webhook.py†L45-L86】 | Trigger maintainer |
| SR-002 | High | Shared secret headers were persisted into workflow run payloads, risking credential leakage. | Added header scrubbing before persistence and coverage at trigger-layer and webhook-state levels. 【F:src/orcheo/triggers/webhook.py†L194-L204】【F:src/orcheo/triggers/layer.py†L132-L151】【F:tests/test_triggers_layer.py†L45-L86】 | Trigger maintainer |
| SR-003 | Medium | Vault audit events lack export hooks for downstream SIEM ingestion. | Track follow-up task to add structured log streaming in Milestone 6. | Platform lead |
| SR-004 | Medium | Rate limiting is process-local; distributed deployments need a shared limiter. | Follow-up backlog item to integrate Redis-backed limiter before production rollout. | Backend lead |
| SR-005 | Medium | Execution workers lack tenant-aware sandbox boundaries for untrusted nodes. | Documented requirement to enforce per-run isolation as part of observability milestone. | Runtime lead |

## Follow-up Actions
- [ ] Design SIEM export pipeline for vault audit trails (SR-003).
- [ ] Integrate distributed rate limiter for webhook triggers (SR-004).
- [ ] Introduce tenant/workspace isolation at execution-worker layer (SR-005).

## Exit Criteria & Sign-off
- ✅ Roadmap item completed; see [Milestone 3 roadmap entry](./roadmap.md#milestone-3-–-credential-vault--security).
- ✅ Linting (`make lint`) and test suite (`make test`) executed successfully.
- ✅ Regression tests added for secret scrubbing and constant-time comparisons.

_Sign-off: Security reviewer, Trigger maintainer, Backend lead_
