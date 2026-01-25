# Requirements Document Template

> **Developer note:** Remove any guidance text written in the `_[text]_` format when producing the final requirements document.

## METADATA
- **Authors:**
- **Project/Feature Name:**
- **Type:** Product | Feature | Enhancement
- **Summary:**
- **Owner (if different than authors):**
- **Date Started:**

## RELEVANT LINKS & STAKEHOLDERS
_[Include only the documents relevant to your project/feature scope]_

| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Prior Artifacts | [Add link] | PM | [Insert name] |
| Design Review | Deck | PM | [Insert name] |
| Design File/Deck | Figma | Designer | [Insert name] |
| Eng Requirement Doc | ERD | Tech Lead | [Insert name] |
| Marketing Requirement Doc (if applicable) | MRD | PMM | [Insert name] |
| Experiment Plan (if applicable) | link | DS | [Insert name] |
| Rollout Docs (if applicable) | GTM & Launch Documentation | Product Ops | [Insert name] |

## PROBLEM DEFINITION
### Objectives
_[Two sentences max. What are you trying to do?]_
[Insert text here]

### Target users
_[Who are you trying to solve the problem for?]_
[Insert text here]

### User Stories
| As a... | I want to... | So that... | Priority | Acceptance Criteria |
|---------|--------------|------------|----------|---------------------|
|         |              |            |          |                     |

### Context, Problems, Opportunities
_[This section should be limited to half a page or less. Cross-link any strategy decks, prior analysis, and prior experiments to keep this section concise while also sourcing your data.]_
_[What problem are we solving, or what opportunity are we going after?]_
_[Problem definition should be framed around exactly what we believe the problem to be with the current customer experience.]_
[Insert text here]

### Product goals and Non-goals
_[What are the product goals? How do users benefit from using this product?]_
_[What are the non-goals?]_
[Insert text here]

## PRODUCT DEFINITION
### Requirements
_[What are you building? What functionality is needed? What are the components? What does it look like? Given the goals, non-goals, and success metrics above, is there a proposed feature prioritization or phasing for the project? For large projects, please categorize requirements blocking an experiment / MVP (P0) vs serving as a future optimization before scaling (P1 or P2) vs out of scope entirely. For most projects, this section should constitute the majority of your PRD, driving clarity amongst your team and among cross-functional partners as to what is being built. It should be treated as an ongoing source of truth until launched.]_
[Insert text or link here]

### Designs (if applicable)
_[Include an overview of the end-to-end design solution. Focus on key screens.]_
[Insert Figma link]
[Insert copy doc]
[Insert text or link here]

### [Optional] Other Teams Impacted
_[Briefly summarize the overall impact on various products, parties, and functions across the ecosystem]_
- [Affected Area]: [Elaboration of effect]
- [Affected Area]: [Elaboration of effect]

## TECHNICAL CONSIDERATIONS
_[The goal of this section is to outline the high level engineering requirement to facilitate the engineering resource planning. Detailed engineering requirements or system design is out of scope for this section.]_

### Architecture Overview
_[For features: How does this fit into the existing system? For products: High-level system design]_
[Insert text or link here]

### Technical Requirements
_[Key technical constraints, dependencies, and implementation considerations]_
[Insert text or link here]

### AI/ML Considerations (if applicable)
_[Only include this section if AI/ML is part of the solution]_

#### Data Requirements
_[What type of data is required? How do you plan to collect it?]_
[Insert text or link here]

#### Algorithm selection
_[Describe your initial thoughts on model selection, and why]_
[Insert text or link here]

#### Model performance requirements
_[What are the requirements on model performance? e.g. accuracy, recall, precision]_
[Insert text or link here]

## MARKET DEFINITION (for products or large features)
_[Skip this section for internal features or enhancements without external market impact]_

### Total Addressable Market
_[What is your TAM?]_
_[What markets are not addressable by this product and why?]_
[Insert text here]

### Launch Exceptions
_(for Product / Product Ops to fill-out)_
_[An exclusion request for specific markets captured in the TAM above.]_

| Market | Status | Considerations & Summary |
|--------|--------|--------------------------|
| [Insert Region, Country, City, etc.] | [Insert Status: No launch/will launch/in discussion] | [Insert Text Here - briefly summarize why this market was requested for exclusion. Provide any relevant links] |

## LAUNCH/ROLLOUT PLAN

### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] [KPI 1] | [Goal] |
| [Secondary] [KPI 2] | [Goal] |
| [Guardrail] [KPI 3] | [Goal] |

### Rollout Strategy
_[For features: How will this be released? (feature flag, gradual rollout, etc.) For products: Full launch plan]_
[Insert text or link here]

### Experiment Plan (if applicable)
_[Provide an overview of the overall experiment approach. A/B test? Switchback? Pre-post? Holdout groups?]_
[Insert text or link here]

### Estimated Launch Phases (if applicable)
_[For phased rollouts, describe each phase and criteria for progression]_

| Phase | Target | Description |
|-------|--------|-------------|
| **Phase 1** | [Insert target: users/markets/percentage] | [Insert Text Here] |
| **Phase 2** | [Insert target] | [Insert Text Here] |

## HYPOTHESIS & RISKS
_[Each hypothesis/risk should be limited to 2-3 sentences (i.e., one sentence for hypothesis, one sentence for confidence in hypothesis). Generally, PRDs should be focused on validating a single hypothesis and no more than two hypotheses.]_
_[Hypothesis: what do you believe to be true, and what do you think will happen if you are correct? Recommend framing your hypothesis in a customer-centric way, while also describing how the user problem impacts metrics.]_
_[Risk: what are potential risk areas for this feature and what could be some unintended consequences?]_
_[Risk Mitigation: for each identified risk, describe the mitigation strategy or contingency plan to address it.]_
[Insert text here]

## APPENDIX
