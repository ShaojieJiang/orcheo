# Beta Onboarding Playbook

This playbook streamlines onboarding for closed-beta participants.

## Quickstart Checklist

1. Install the Orcheo CLI and dependencies via `uv sync --all-groups`.
2. Seed a workspace using `uv run orcheo init --template slack-notify`.
3. Configure credential templates through `POST /api/credential-templates/{slug}`.
4. Import starter workflows into the canvas using the JSON import feature.

## Feedback & A/B Loops

- Weekly office hours capture qualitative feedback and stack-ranked pain points.
- Built-in chat handoff panel gathers conversational insights for AI assistance.
- Feature toggles gate experimental nodes; run `uv run orcheo metrics` to submit
  anonymized usage stats.

## Reliability Validation

- Nightly smoke tests execute templated workflows across trigger types.
- Load testing exercises the canvas WebSocket bridge with synthetic updates.
- Guardrail node assertions enforce latency and token thresholds before
  production publish.
