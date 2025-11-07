import { Button } from "@/design-system/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { History, RotateCcw, RotateCw } from "lucide-react";

import type { WorkflowControlsProps } from "./types";

type HistoryControlGroupProps = Pick<
  WorkflowControlsProps,
  "onUndo" | "onRedo" | "canUndo" | "canRedo"
>;

export function HistoryControlGroup({
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
}: HistoryControlGroupProps) {
  return (
    <div className="flex items-center gap-1 border border-border rounded-md bg-background p-1">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onUndo}
              disabled={!canUndo}
              aria-label="Undo"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Undo (Ctrl+Z)</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onRedo}
              disabled={!canRedo}
              aria-label="Redo"
            >
              <RotateCw className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Redo (Ctrl+Y)</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              aria-label="History"
            >
              <History className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>History</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
