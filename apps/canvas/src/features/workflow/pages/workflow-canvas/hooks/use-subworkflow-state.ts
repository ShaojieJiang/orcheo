import { useState } from "react";

import type { SubworkflowTemplate } from "@features/workflow/components/panels/workflow-governance-panel";

const DEFAULT_SUBWORKFLOWS: SubworkflowTemplate[] = [
  {
    id: "subflow-customer-onboarding",
    name: "Customer Onboarding Foundation",
    description:
      "Qualify leads, enrich CRM details, and orchestrate the welcome sequence.",
    tags: ["crm", "sales", "email"],
    version: "1.3.0",
    status: "stable",
    usageCount: 18,
    lastUpdated: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
  },
  {
    id: "subflow-incident-response",
    name: "Incident Response Escalation",
    description:
      "Route Sev1 incidents, notify stakeholders, and collect on-call context.",
    tags: ["ops", "pagerduty", "slack"],
    version: "0.9.2",
    status: "beta",
    usageCount: 7,
    lastUpdated: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(),
  },
  {
    id: "subflow-content-qa",
    name: "Content QA & Publishing",
    description:
      "Score AI-generated drafts, request revisions, and schedule approved posts.",
    tags: ["marketing", "ai", "review"],
    version: "2.0.0",
    status: "stable",
    usageCount: 11,
    lastUpdated: new Date(Date.now() - 1000 * 60 * 60 * 24 * 6).toISOString(),
  },
];

export function useSubworkflowState(
  initial: SubworkflowTemplate[] = DEFAULT_SUBWORKFLOWS,
) {
  const [subworkflows, setSubworkflows] =
    useState<SubworkflowTemplate[]>(initial);
  return { subworkflows, setSubworkflows };
}
