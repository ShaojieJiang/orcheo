import type { WorkflowRunnableConfig } from "@features/workflow/lib/workflow-storage.types";
import type { Workflow } from "../workflow-types";

export interface WorkflowTemplateDefinition {
  workflow: Workflow;
  script: string;
  entrypoint?: string;
  runnableConfig?: WorkflowRunnableConfig | null;
  notes: string;
}
