import React from "react";

import { cn } from "@/lib/utils";

import { ActionControlGroup } from "./workflow-controls/action-control-group";
import { HistoryControlGroup } from "./workflow-controls/history-control-group";
import type { WorkflowControlsProps } from "./workflow-controls/types";

export default function WorkflowControls({
  isRunning = false,
  onRun,
  onPause,
  onSave,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
  onDuplicate,
  onExport,
  onImport,
  onShare,
  onVersionHistory,
  onToggleSearch,
  isSearchOpen = false,
  className,
}: WorkflowControlsProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <ActionControlGroup
        isRunning={isRunning}
        onPause={onPause}
        onRun={onRun}
        onSave={onSave}
        onDuplicate={onDuplicate}
        onExport={onExport}
        onImport={onImport}
        onShare={onShare}
        onVersionHistory={onVersionHistory}
        onToggleSearch={onToggleSearch}
        isSearchOpen={isSearchOpen}
      />
      <HistoryControlGroup
        onUndo={onUndo}
        onRedo={onRedo}
        canUndo={canUndo}
        canRedo={canRedo}
      />
    </div>
  );
}
