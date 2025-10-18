# Vault, Trigger, and Execution Surface Security Review

This document summarizes the 2025-01-15 security review covering Orcheo's
credential vault, trigger orchestration layer, and execution runtime. The
assessment combined automated checks, manual threat modeling, and targeted
penetration tests.

## Methodology
- **Threat Modeling Workshops:** Facilitated cross-functional sessions to
  enumerate assets, entry points, and abuse cases. We tracked STRIDE coverage for
  the vault, trigger APIs, LangGraph execution, and WebSocket telemetry.
- **Penetration Testing:** Conducted authenticated and anonymous probing of the
  FastAPI surface, including credential issuance endpoints, webhook dispatch,
  cron scheduling, and manual trigger APIs. Replay and concurrency scenarios were
  exercised to validate optimistic locking.
- **Static & Dynamic Analysis:** `ruff`, `mypy`, Bandit, and OWASP ZAP scans were
  executed against the backend. Runtime monitoring validated that credential
  secrets remain encrypted at rest and scrubbed from logs.

## Vault Findings
- AES-GCM encryption keys are generated per-environment with rotation hooks.
- Credential templates enforce format validation and rotation SLAs. Governance
  alerts route to the security channel when rotation thresholds lapse or health
  checks report failures.
- OAuth refresh flows reject provider mismatches, preventing token reuse across
  workflows.
- No critical or high findings. Medium risk: add rate limits to credential
  issuance endpoints (tracked in backlog ticket SEC-112).

## Trigger & Execution Findings
- Health guards block trigger execution when credential status is unhealthy.
- Cron, manual, and webhook dispatch paths enforce per-workflow concurrency and
  audit every transition.
- Penetration testing confirmed signature validation on webhook triggers and
  replay protection for manual dispatch.
- Observability instrumentation captures per-step metrics, enabling anomaly
  detection without leaking secret material.

## Mitigations & Follow-up
1. Roll out global rate limits and IP allowlists for credential issuance APIs.
2. Expand fuzz testing for the JSON import/export pipeline used by the canvas.
3. Integrate credential governance alerts into the ops on-call rotation.
4. Re-run the full assessment prior to v1.0 code freeze.

_Review completed by the Orcheo security engineering team._
