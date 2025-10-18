# Orcheo Onboarding Playbook

This playbook documents the assets and feedback loops used to onboard beta teams
into Orcheo.

## Templates & Quickstarts
- **Credential Templates:** Auto-issued via `/api/credentials/templates` with
  governance alerts surfaced in the UI.
- **Workflow Library:** Canvas templates cover lead welcome, nightly sync, and
  webhook-to-agent flows with credential assignments baked in.
- **SDK Quickstarts:** `examples/` folder showcases SDK ingestion, trigger
  dispatch, and WebSocket monitoring. Each sample links to docs via README call
  outs.

## Closed Beta Operating Rhythm
1. **Invite Cohorts:** Weekly invites with 30 minute guided session.
2. **Feedback Capture:** In-app chat panel routes transcripts to the product
   channel using the new guardrails node to tag sentiment.
3. **A/B Testing:** Latency metrics from `get_metrics_recorder()` feed into a
   dashboard comparing control vs experiment templates.
4. **Success Metrics:** Track quickstart completion rate, credential validation
   failures, and canvas publish success using the metrics recorder summaries.

## Phase Gates
- **Phase 1:** Internal dogfooding with 3 teams validating trigger health and
  canvas publishing.
- **Phase 2:** External partners with SSO, audit logging, and workflow
  marketplace pilots.

_Updated: 2025-01-15_
