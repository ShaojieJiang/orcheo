# Requirements Document

## METADATA
- **Authors:** Codex
- **Project/Feature Name:** Canvas Workflow Visualisation
- **Type:** Enhancement
- **Summary:** Simplify LangGraph-first Canvas workflow authoring by removing legacy Editor/Execution tabs, introducing a Workflow Mermaid visualisation tab with reusable workflow config form, and making gallery workflow cards directly clickable.
- **Owner (if different than authors):** Shaojie Jiang
- **Date Started:** 2026-02-20

## RELEVANT LINKS & STAKEHOLDERS

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Requirements | `./1_requirements.md` | Shaojie Jiang | Canvas workflow visualisation requirements |
| Design | `./2_design.md` | Shaojie Jiang | Canvas workflow visualisation design |
| Plan | `./3_plan.md` | Shaojie Jiang | Canvas workflow visualisation implementation plan |
| Current Tabs UI | `apps/canvas/src/features/workflow/components/panels/workflow-tabs.tsx` | Shaojie Jiang | Existing tab definitions |
| Current Canvas Layout | `apps/canvas/src/features/workflow/pages/workflow-canvas/components/workflow-canvas-layout.tsx` | Shaojie Jiang | Existing tab content wiring |
| Current Node Config Form | `apps/canvas/src/features/workflow/components/panels/node-inspector/config-panel.tsx` | Shaojie Jiang | RJSF-based node configuration form |
| Current Gallery Card | `apps/canvas/src/features/workflow/pages/workflow-gallery/workflow-card.tsx` | Shaojie Jiang | Workflow gallery card interactions |

## PROBLEM DEFINITION
### Objectives
Reduce workflow UI complexity and shift the primary workflow view to diagram-first visualization for LangGraph workflows. Ensure users can access workflow configuration from the new Workflow tab and navigate faster from the gallery by clicking cards directly.

### Target users
- Canvas users viewing and configuring workflows
- Workflow authors importing LangGraph workflows and validating graph structure
- Operators browsing workflows in the gallery

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
| Workflow user | See a Workflow tab with Mermaid diagram | I can quickly understand workflow structure | P0 | Workflow page exposes a `Workflow` tab that renders Mermaid for the active workflow version |
| Workflow user | Configure workflow runtime settings from Workflow tab | I can edit workflow-level config without switching contexts | P0 | Workflow tab has a config button opening a workflow config form reusing node form infrastructure |
| Product team | Remove Editor/Execution tabs from primary experience | UI is focused and aligned to visualization-first direction | P0 | `Editor` and `Execution` tabs are removed from the active tabs list |
| Engineering team | Preserve old Editor/Execution implementation in legacy location | We can rollback/reference old behavior safely | P0 | Legacy tab implementations are moved under `apps/canvas/src/features/workflow/legacy/` and are not wired to active UI |
| Gallery user | Click anywhere on workflow cards to open workflow | Navigation is faster and more intuitive | P0 | Clicking the card body navigates to the workflow canvas; action menu buttons remain functional |

### Context, Problems, Opportunities
The current workflow canvas uses tab labels `Editor`, `Execution`, `Trace`, `Readiness`, and `Settings`. `Editor` and `Execution` currently represent large feature surfaces that dilute the intended visualisation flow. In parallel, workflow gallery interaction requires clicking smaller CTA controls rather than the card itself. Since the target experience is LangGraph-first, the opportunity is to reduce friction by promoting a dedicated `Workflow` visualization tab with Mermaid rendering from backend workflow version payloads, preserving old code under a legacy boundary, and improving navigation ergonomics via clickable cards.

### Product goals and Non-goals
Goals:
- Replace Editor/Execution entry points with a Workflow-centric visualisation tab.
- Reuse existing node configuration form stack (RJSF templates/widgets/validator) for workflow-level config.
- Keep implementation reversible through a clean legacy folder move.
- Improve gallery open-workflow discoverability through card-level click.

Non-goals:
- Redesigning Trace, Readiness, or Settings experiences.
- Rebuilding workflow editing/execution behavior in this initiative.
- Introducing a new form framework (must reuse current node config form infrastructure).

## PRODUCT DEFINITION
### Requirements
- **P0: Tab restructuring**
  - Remove `Editor` and `Execution` tab triggers from active tabs UI.
  - Add a `Workflow` tab in the same tab bar.
  - Ensure default active tab is updated from `"canvas"` to `"workflow"` for new sessions.
- **P0: Legacy code migration**
  - Move code currently used by removed tabs into a legacy directory under `apps/canvas/src/features/workflow/legacy/`.
  - Retain code for reference/rollback, but detach from active imports.
- **P0: Workflow Mermaid view**
  - Workflow tab renders Mermaid diagram for current workflow version.
  - Mermaid source is provided by backend workflow version payload (`ApiWorkflowVersion.mermaid`) so frontend and CLI show consistent diagrams.
  - Handle empty/invalid graph states with clear fallback messaging.
- **P0: Workflow config via reused form**
  - Workflow tab includes a Config button.
  - Config button opens workflow config form using same RJSF setup used by node config forms (`customWidgets`, `customTemplates`, `validator`).
  - Workflow config persists only on explicit config save action from the Workflow tab.
  - Saved workflow config maps to workflow version payloads (`runnable_config`).
- **P0: Clickable workflow cards**
  - Make non-template workflow gallery cards clickable in the card body area.
  - Preserve dropdown/menu/button controls without accidental navigation.

### Designs (if applicable)
See `./2_design.md` for component boundaries, API/data contract updates, and migration details.

### Other Teams Impacted
- Backend API team: expose Mermaid in workflow version API payloads for Canvas consumption.
- QA: regression tests for tab navigation, workflow config modal/sheet, and gallery card click behavior.

## TECHNICAL CONSIDERATIONS
### Architecture Overview
The Canvas workflow page replaces tab routing for Editor/Execution with a new Workflow tab surface and keeps trace/readiness/settings intact. Existing Editor/Execution components move to a confirmed legacy namespace (`apps/canvas/src/features/workflow/legacy/`) to preserve implementation history. Workflow tab consumes backend-provided Mermaid from workflow version payloads and renders it, while a workflow-level config UI reuses the node inspector form foundation and persists only on explicit save. Gallery cards become clickable wrappers with guarded event propagation for inner actions.

### Technical Requirements
- Update active tab definitions in:
  - `apps/canvas/src/features/workflow/components/panels/workflow-tabs.tsx`
  - `apps/canvas/src/features/workflow/pages/workflow-canvas/components/workflow-canvas-layout.tsx`
  - `apps/canvas/src/features/workflow/pages/workflow-canvas/hooks/use-canvas-ui-state.ts`
  - `apps/canvas/src/features/workflow/pages/workflow-canvas/hooks/controller/build-layout-props.ts`
- Create legacy folder for removed tab code:
  - `apps/canvas/src/features/workflow/legacy/` (structure defined in design doc)
- Reuse RJSF tooling from:
  - `apps/canvas/src/features/workflow/components/panels/rjsf-theme.tsx`
  - `apps/canvas/src/features/workflow/components/panels/node-inspector/config-panel.tsx`
- Extend workflow version typing for config persistence visibility:
  - `apps/canvas/src/features/workflow/lib/workflow-storage.types.ts`
- Add Mermaid in workflow version API payload returned by backend:
  - `apps/backend/src/orcheo_backend/app/routers/workflows.py`
  - `apps/backend/src/orcheo_backend/app/schemas/workflows.py` (if response schema changes are introduced)
  - `src/orcheo/models/workflow_entities.py` (if `WorkflowVersion` response model is expanded)
- Make card-level navigation changes in:
  - `apps/canvas/src/features/workflow/pages/workflow-gallery/workflow-card.tsx`

### AI/ML Considerations (if applicable)
Not applicable.

## MARKET DEFINITION
Internal product enhancement; no external market scope.

## LAUNCH/ROLLOUT PLAN

### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| Primary: Workflow tab usage | 100% of workflow page sessions land in new `Workflow` tab |
| Secondary: Gallery open success | No drop in workflow open rate after card click behavior change |
| Guardrail: Config save reliability | 0 critical errors in workflow config form open/save flows |

### Rollout Strategy
Release behind a frontend feature flag (if available) or staged branch release. Validate in dev/staging with migration checklist before enabling by default.

### Experiment Plan (if applicable)
Not required.

### Estimated Launch Phases (if applicable)
| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | Internal dev/staging | Validate tab migration, Mermaid rendering, config form reuse, and clickable card interactions |
| **Phase 2** | Production | Enable for all Canvas users with updated tests and docs |

## HYPOTHESIS & RISKS
Hypothesis: replacing Editor/Execution entry points with Workflow visualization and direct card click navigation will reduce navigation friction and improve workflow comprehension. Primary risks are loss of discoverability for legacy actions and regressions from moving tab code. Mitigations: preserve legacy code under a clear namespace, add focused regression tests around tab behavior and card action propagation, and provide fallback messaging when Mermaid data is unavailable.

## APPENDIX
None.
