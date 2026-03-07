import { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import { PYTHON_AGENT_TEMPLATE, PYTHON_AGENT_WORKFLOW } from "./python-agent";

export const SAMPLE_WORKFLOWS: Workflow[] = [PYTHON_AGENT_WORKFLOW];

export const WORKFLOW_TEMPLATE_DEFINITIONS: WorkflowTemplateDefinition[] = [
  PYTHON_AGENT_TEMPLATE,
];

const TEMPLATE_BY_ID = new Map(
  WORKFLOW_TEMPLATE_DEFINITIONS.map((definition) => [
    definition.workflow.id,
    definition,
  ]),
);

export const getWorkflowTemplateDefinition = (
  templateId: string,
): WorkflowTemplateDefinition | undefined => {
  return TEMPLATE_BY_ID.get(templateId);
};

export { TEMPLATE_OWNER, PYTHON_AGENT_WORKFLOW, PYTHON_AGENT_TEMPLATE };
