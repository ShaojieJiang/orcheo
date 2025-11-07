import { cn } from "@/lib/utils";

import { SubworkflowListCard } from "./workflow-governance-panel/subworkflow-list-card";
import { ValidationSection } from "./workflow-governance-panel/validation-section";
import type { WorkflowGovernancePanelProps } from "./workflow-governance-panel/types";

export default function WorkflowGovernancePanel({
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
  className,
}: WorkflowGovernancePanelProps) {
  return (
    <div className={cn("space-y-6", className)}>
      <SubworkflowListCard
        subworkflows={subworkflows}
        onCreateSubworkflow={onCreateSubworkflow}
        onInsertSubworkflow={onInsertSubworkflow}
        onDeleteSubworkflow={onDeleteSubworkflow}
      />
      <ValidationSection
        validationErrors={validationErrors}
        isValidating={isValidating}
        onRunValidation={onRunValidation}
        onDismissValidation={onDismissValidation}
        onFixValidation={onFixValidation}
        lastValidationRun={lastValidationRun}
      />
    </div>
  );
}

export type {
  SubworkflowTemplate,
  WorkflowGovernancePanelProps,
} from "./workflow-governance-panel/types";
