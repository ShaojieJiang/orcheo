import React from "react";

import WorkflowExecutionHistory from "@features/workflow/components/panels/workflow-execution-history";
import type { WorkflowExecution } from "@features/workflow/pages/workflow-canvas/helpers/types";

export interface ExecutionTabContentProps {
  executions: WorkflowExecution[];
  onViewDetails: (
    execution: React.ComponentProps<
      typeof WorkflowExecutionHistory
    >["executions"][number],
  ) => void;
  onRefresh: () => void;
  onCopyToEditor: (
    execution: React.ComponentProps<
      typeof WorkflowExecutionHistory
    >["executions"][number],
  ) => void;
  onDelete: (
    execution: React.ComponentProps<
      typeof WorkflowExecutionHistory
    >["executions"][number],
  ) => void;
  onRunWorkflow: () => void;
  onPauseWorkflow: () => void;
  isRunning: boolean;
  activeExecutionId: string | null;
  setActiveExecutionId: (value: string | null) => void;
}

export function ExecutionTabContent({
  executions,
  onViewDetails,
  onRefresh,
  onCopyToEditor,
  onDelete,
  onRunWorkflow,
  onPauseWorkflow,
  isRunning,
  activeExecutionId,
  setActiveExecutionId,
}: ExecutionTabContentProps) {
  return (
    <WorkflowExecutionHistory
      executions={executions}
      onViewDetails={onViewDetails}
      onRefresh={onRefresh}
      onCopyToEditor={onCopyToEditor}
      onDelete={onDelete}
      onRunWorkflow={onRunWorkflow}
      onPauseWorkflow={onPauseWorkflow}
      isRunning={isRunning}
      activeExecutionId={activeExecutionId}
      onActiveExecutionChange={setActiveExecutionId}
    />
  );
}
