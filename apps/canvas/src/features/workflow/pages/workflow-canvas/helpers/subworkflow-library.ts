import { contentQaSubworkflow } from "./subworkflows/content-qa";
import { customerOnboardingSubworkflow } from "./subworkflows/customer-onboarding";
import { incidentResponseSubworkflow } from "./subworkflows/incident-response";
import type { SubworkflowStructure } from "./subworkflows/types";

export const SUBWORKFLOW_LIBRARY: Record<string, SubworkflowStructure> = {
  "subflow-customer-onboarding": customerOnboardingSubworkflow,
  "subflow-incident-response": incidentResponseSubworkflow,
  "subflow-content-qa": contentQaSubworkflow,
};

export type { SubworkflowStructure };
