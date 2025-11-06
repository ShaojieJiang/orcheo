import React from "react";

import WorkflowGovernancePanel from "@features/workflow/components/panels/workflow-governance-panel";

import type { ValidationError } from "@features/workflow/components/canvas/connection-validator";
import type { SubworkflowTemplate } from "@features/workflow/components/panels/workflow-governance-panel";

export interface ReadinessTabContentProps {
  subworkflows: SubworkflowTemplate[];
  onCreateSubworkflow: () => void;
  onInsertSubworkflow: (template: SubworkflowTemplate) => void;
  onDeleteSubworkflow: (templateId: string) => void;
  validationErrors: ValidationError[];
  onRunValidation: () => void;
  onDismissValidation: () => void;
  onFixValidation: () => void;
  isValidating: boolean;
  lastValidationRun: string | null;
}

export function ReadinessTabContent({
  subworkflows,
  onCreateSubworkflow,
  onInsertSubworkflow,
  onDeleteSubworkflow,
  validationErrors,
  onRunValidation,
  onDismissValidation,
  onFixValidation,
  isValidating,
  lastValidationRun,
}: ReadinessTabContentProps) {
  return (
    <div className="mx-auto max-w-5xl pb-12">
      <WorkflowGovernancePanel
        subworkflows={subworkflows}
        onCreateSubworkflow={onCreateSubworkflow}
        onInsertSubworkflow={onInsertSubworkflow}
        onDeleteSubworkflow={onDeleteSubworkflow}
        validationErrors={validationErrors}
        onRunValidation={onRunValidation}
        onDismissValidation={onDismissValidation}
        onFixValidation={onFixValidation}
        isValidating={isValidating}
        lastValidationRun={lastValidationRun}
      />
    </div>
  );
}
