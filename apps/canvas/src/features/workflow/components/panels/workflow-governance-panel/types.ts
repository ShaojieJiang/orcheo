import type { ValidationError } from "../canvas/connection-validator";

export interface SubworkflowTemplate {
  id: string;
  name: string;
  description: string;
  tags: string[];
  version: string;
  status: "stable" | "beta" | "deprecated";
  usageCount: number;
  lastUpdated: string;
}

export interface WorkflowGovernancePanelProps {
  subworkflows: SubworkflowTemplate[];
  onCreateSubworkflow: () => void;
  onInsertSubworkflow: (subworkflow: SubworkflowTemplate) => void;
  onDeleteSubworkflow: (id: string) => void;
  validationErrors: ValidationError[];
  onRunValidation: () => void;
  onDismissValidation: (id: string) => void;
  onFixValidation: (error: ValidationError) => void;
  isValidating: boolean;
  lastValidationRun?: string | null;
  className?: string;
}
