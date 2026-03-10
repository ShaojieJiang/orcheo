import { Workflow } from "../workflow-types";
import type { WorkflowTemplateDefinition } from "./template-definition";
import { TEMPLATE_OWNER } from "./template-owner";
import {
  MONGODB_QA_AGENT_TEMPLATE,
  MONGODB_QA_AGENT_WORKFLOW,
} from "./mongodb-qa-agent";
import { PYTHON_AGENT_TEMPLATE, PYTHON_AGENT_WORKFLOW } from "./python-agent";
import {
  TELEGRAM_HELLO_TEMPLATE,
  TELEGRAM_HELLO_WORKFLOW,
} from "./telegram-hello";
import {
  TELEGRAM_AGENT_TEMPLATE,
  TELEGRAM_AGENT_WORKFLOW,
} from "./telegram-agent";

export const SAMPLE_WORKFLOWS: Workflow[] = [
  PYTHON_AGENT_WORKFLOW,
  TELEGRAM_HELLO_WORKFLOW,
  TELEGRAM_AGENT_WORKFLOW,
  MONGODB_QA_AGENT_WORKFLOW,
];

export const WORKFLOW_TEMPLATE_DEFINITIONS: WorkflowTemplateDefinition[] = [
  PYTHON_AGENT_TEMPLATE,
  TELEGRAM_HELLO_TEMPLATE,
  TELEGRAM_AGENT_TEMPLATE,
  MONGODB_QA_AGENT_TEMPLATE,
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

export {
  TEMPLATE_OWNER,
  MONGODB_QA_AGENT_TEMPLATE,
  MONGODB_QA_AGENT_WORKFLOW,
  PYTHON_AGENT_TEMPLATE,
  PYTHON_AGENT_WORKFLOW,
  TELEGRAM_AGENT_TEMPLATE,
  TELEGRAM_AGENT_WORKFLOW,
  TELEGRAM_HELLO_TEMPLATE,
  TELEGRAM_HELLO_WORKFLOW,
};
