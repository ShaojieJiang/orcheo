import type { Workflow } from "../workflow-types";

export interface WorkflowTemplateDefinition {
  workflow: Workflow;
  script: string;
  entrypoint?: string;
  notes: string;
}
