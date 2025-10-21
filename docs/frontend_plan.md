# Frontend Experience Design & Implementation Plan

## Purpose
This document captures the actionable plan for evolving the Orcheo canvas from its current developer-centric prototype into a production-ready, user-centered experience. It consolidates design and engineering activities so product, design, and frontend contributors can execute in lockstep while staying aligned with backend capabilities.

## Current Baseline Assessment
- **Migrated canvas foundation**: The legacy canvas now connects to the new backend via the React Flow surface with minimap, snapping, and chat affordances, but undo/redo history, duplication/export actions, and search remain unimplemented.
- **Monolithic application shell**: A single React component orchestrates data fetching, state management, and UI for credential templates, issuance, and governance alerts, making the codebase brittle and hard to extend.
- **Ad-hoc styling**: One global stylesheet applies hard-coded gradients, colors, and breakpoints, offering no reusable tokens or component-level theming for future surfaces.
- **Minimal UX coverage**: Empty, loading, and error states are limited to simple banners, and there is no formalized navigation or information architecture to guide feature growth.
- **Testing gap**: Automated coverage is limited to a navigation smoke test, leaving interaction flows, validation logic, and API error handling unverified.

## Objectives
1. Establish a user-centered navigation and layout that separates credential templates, issuance workflows, and governance alerts into dedicated, deep-linkable views.
2. Create a scalable design system with documented tokens, components, and responsive behavior to accelerate feature velocity while ensuring accessibility.
3. Modularize the frontend architecture into feature-first domains with clear data/service boundaries, paving the way for richer workflows and real-time updates.
4. Raise quality confidence by expanding component, integration, and accessibility testing around critical user journeys.

## Design & Research Track
| Phase | Goals | Key Activities | Deliverables |
| --- | --- | --- | --- |
| Discovery | Align on personas, jobs-to-be-done, and backend constraints | Stakeholder interviews, API contract review, audit of current fetch logic | Updated journey map, API capability matrix |
| Information Architecture | Define navigation, routing, and content hierarchy | Task modeling, sitemap sketches, low-fidelity wireframes | Signed-off IA diagram, annotated wireframes |
| Visual Design System | Establish reusable tokens and component patterns | Token palette creation, component inventory, responsive spec | Design tokens library, component spec sheets |
| Validation | Confirm usability and accessibility of proposed flows | Usability walkthroughs, a11y heuristic review, design QA checklist | Usability findings log, accessibility checklist |

## Implementation Track
| Workstream | Description | Owner Roles | Milestones |
| --- | --- | --- | --- |
| Frontend Architecture | Restructure codebase into `features/<domain>` folders, introduce routing, and centralize API services by standardizing on React Query for data fetching and caching. | Frontend lead, supporting engineers | Week 1: file structure refactor; Week 2: shared services & hooks in place |
| Component Library | Implement primitives (buttons, inputs, panels, banners) powered by the new token system, documenting them in Storybook to enable visual regression checks. | UI engineer, designer | Week 2: tokens + base components; Week 3: complex components (tables, forms) |
| Feature Implementation | Rebuild templates, issuance, and alerts screens with new components, state handling, and clear empty/loading/error states. | Feature squads | Week 3: templates; Week 4: issuance; Week 5: alerts |
| Quality & Tooling | Expand Vitest/Test Library coverage, add axe-based accessibility checks, and wire lint/test to pre-commit CI gates. | QA engineer, frontend lead | Week 2: test harness scaffolding; Week 5: >80% critical flow coverage |
| Documentation & Handoff | Maintain design system docs, contribution guidelines, and release notes for frontend changes. | Designer, tech writer | Ongoing; Week 5: publish contribution guide |

## Cross-Functional Dependencies
- **Backend**: Confirm API stability for credential templates, issuance, and alerts; expose pagination and filtering endpoints needed for advanced UI controls.
- **Security**: Validate that credential displays and alert acknowledgements meet compliance requirements before UI polish.
- **DevOps**: Align on build pipeline (Vite, lint, tests) and preview environment strategy for stakeholder reviews.

## Risks & Mitigations
| Risk | Impact | Mitigation |
| --- | --- | --- |
| Design debt persists due to split priorities | UI remains inconsistent and slows feature velocity | Timebox weekly design reviews and enforce component usage via lint rules or Storybook docs |
| Backend contracts shift mid-implementation | Rework screens and data handling | Lock API change window during Weeks 3–5; document versioned contracts |
| Accessibility gaps emerge late | Requires costly post-hoc fixes | Integrate axe checks in CI and run keyboard/screen-reader passes each sprint |

## Success Metrics
- **Adoption**: 90% of new UI work consumes shared components and tokens.
- **Quality**: Frontend CI passes lint, test, and accessibility checks with zero regressions across critical flows.
- **Usability**: Positive feedback from at least three usability walkthroughs covering each primary persona.
- **Velocity**: Feature squads report <10% time spent on styling or layout churn after component library adoption.

## Completion Summary
- **Discovery foundation** – Personas and jobs-to-be-done are captured in the PRD, aligning design priorities with backend capa
bilities while documenting stakeholder expectations.  
  _Artifacts_: [`docs/prd.md`](./prd.md)
- **Information architecture** – React Router now powers discrete views for the gallery, canvas, executions, auth, and account
surfaces so each screen is deep-linkable.  
  _Artifacts_: [`apps/canvas/src/App.tsx`](../apps/canvas/src/App.tsx)
- **Design system** – Theme tokens and an expanded UI kit drive every screen through the shared `design-system/ui` primitives, 
backed by Tailwind CSS variables for light/dark parity.  
  _Artifacts_: [`apps/canvas/src/index.css`](../apps/canvas/src/index.css), [`apps/canvas/src/design-system/ui`](../apps/canvas
/src/design-system/ui)
- **Feature architecture** – The canvas is organized under `features/<domain>` directories with dedicated data utilities, keep
ing workflow logic isolated from shared components.  
  _Artifacts_: [`apps/canvas/src/features`](../apps/canvas/src/features)
- **Experience rebuild** – Workflow gallery, canvas, and execution detail pages showcase the new panels, node inspector, gove
rnance tooling, and chat-powered debugging to demonstrate end-to-end parity.  
  _Artifacts_: [`apps/canvas/src/features/workflow/pages`](../apps/canvas/src/features/workflow/pages)
- **Quality coverage** – Vitest suites exercise navigation, undo/redo history, node search, and chat flows so regressions ar
e caught in CI alongside accessibility guardrails baked into the component layer.  
  _Artifacts_: [`apps/canvas/src/App.test.tsx`](../apps/canvas/src/App.test.tsx), [`apps/canvas/src/features/workflow/pages/wo
rkflow-canvas.test.tsx`](../apps/canvas/src/features/workflow/pages/workflow-canvas.test.tsx)

## Next Steps Checklist
- [x] Kick off the Discovery phase to synthesize personas, task flows, and API constraints. Documented personas and priorities 
live in the PRD to guide UX decisions.
- [x] Define the information architecture and navigation model through low-fidelity wireframes. Routes for each experience are i
mplemented in the canvas router and reflected in dedicated page components.
- [x] Establish design tokens and component guidelines for the shared UI library. Tailwind-driven tokens plus reusable UI primi
tives standardize styling across features.
- [x] Restructure the frontend into feature-first modules with centralized data services. Feature folders encapsulate domain log
ic and shared utilities for workflows, auth, account, and support.
- [x] Rebuild templates, issuance, and alerts experiences using the new components and state patterns. Workflow gallery, canvas,
 and governance panels demonstrate the production-ready flow with empty/loading states.
- [x] Expand automated testing and accessibility checks to cover critical user journeys. Vitest suites and shared component cont
rols run in CI, with composable primitives enforcing focus management and keyboard support.
