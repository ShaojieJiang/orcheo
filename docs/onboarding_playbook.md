# Orcheo Onboarding Playbook

## Getting Started Checklist
1. Install dependencies with `uv sync --all-groups`.
2. Launch the FastAPI backend via `make dev-server`.
3. Start the canvas designer (this app) with `npm install && npm run dev`.
4. Use the workflow templates in the designer to create your first automation.

## Credential Templates
- Issue sample credentials directly from the designer.
- Governance alerts highlight expiring OAuth tokens or missing validation.

## SDK Examples
- The SDK includes helpers for triggering runs and polling execution history.
- See `examples/` for authenticated HTTP requests and template ingestion flows.

## Feedback Loop
- Use the chat console to leave inline feedback during workflow testing.
- Metrics are aggregated in `observability.md` for tracking quickstart completion rates.
