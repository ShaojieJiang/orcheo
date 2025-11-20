# PRD Template

## METADATA
- **Authors:**
- **Project name (if applicable):**
- **Product Summary:**
- **Owner (if different than authors):**
- **Date Started:**

## RELEVANT LINKS & STAKEHOLDERS
| Documents | Link | Owner | Name |
|-----------|------|-------|------|
| Prior Artifacts | [Add link] | PM | [Insert name] |
| PRD / Design Review | Deck | PM | [Insert name] |
| Design File/Deck | Figma | Designer | [Insert name] |
| Eng Requirement Doc | ERD | Tech Lead | [Insert name] |
| Marketing Requirement Doc | MRD | PMM | [Insert name] |
| Experiment Plan | link | DS | [Insert name] |
| Product Rollout Docs | GTM & Launch Documentation | Product Ops | [Insert name] |

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

### Why AI?
_[Explain why AI is required/preferred for solving this problem]_
[Insert text or link here]

### Data Requirements
_[What type of data is required for training the AI model? How do you plan to collect them?]_
[Insert text or link here]

### Algorithm selection
_[Describe your initial thoughts on model selection, and why]_
[Insert text or link here]

### Model performance requirements
_[Based on the product design, what’s the requirements on model performance? e.g. accuracy, recall, precision]_
[Insert text or link here]

### Engineering resource
_[Estimate of # of DS, MLE, BE, FE, Designer, etc, and eng weeks]_
[Insert text or link here]

## MARKET DEFINITION
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

## LAUNCH PLAN
### Experiment Plan
_[Provide an overview of the overall experiment approach. A/B test? Switchback? Pre-post? Holdout groups? The details of the experiment should be captured in the experiment plan driven by DS. Document where your XP will launch and should consider a market in each mega-region covered by your TAM]_
[Insert text or link here]

### Success metrics
| KPIs | Target & Rationale |
|------|--------------------|
| [Primary] [KPI 1] | [Goal] |
| [Secondary] [KPI 2] | [Goal] |
| [Guardrail] [KPI 3] | [Goal] |

### Estimated Geo Launch Phases (if applicable)
_[Enter the estimated timeline using the expected month for each step. The intent is less on date precision but articulating why this product may need to roll out in phases to the TAM outlined above. The sum of all launch phases should equal the TAM minus any approved exclusion requests]_

| XP launch | [Insert Month] | [Insert Text Here] |
|-----------|----------------|---------------------|
| **Phase 1 Launch** | [Insert Estimated Month or Quarter] | [Insert Text Here] _[List markets that will receive the feature in this phase. Outline why any markets will **not** receive this feature in this phase]_ |
| **Phase 2 Launch** | [Insert Estimated Month or Quarter] | [Insert Text Here] _[List markets that will receive the feature in this phase. Outline why any markets will **not** receive this feature in this phase]_ |

### Pricing strategy (if applicable)
_[How do you price your product and why]_
[Insert text or link here]

## HYPOTHESIS & RISKS
_[Each hypothesis/risk should be limited to 2-3 sentences (i.e., one sentence for hypothesis, one sentence for confidence in hypothesis). Generally, PRDs should be focused on validating a single hypothesis and no more than two hypotheses.]_
_[Hypothesis: what do you believe to be true, and what do you think will happen if you are correct? Recommend framing your hypothesis in a customer-centric way, while also describing how the user problem impacts metrics.]_
_[Risk: what are potential risk areas for this feature and what could be some unintended consequences?]_
[Insert text here]

## APPENDIX
