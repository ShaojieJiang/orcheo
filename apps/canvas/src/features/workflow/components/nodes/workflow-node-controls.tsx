import React from "react";
import { Play, Settings, ToggleLeft, Trash } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { cn } from "@/lib/utils";

interface WorkflowNodeControlsProps {
  visible: boolean;
  isDisabled?: boolean;
  nodeId: string;
  onDelete?: (id: string) => void;
}

export const WorkflowNodeControls = React.forwardRef<
  HTMLDivElement,
  WorkflowNodeControlsProps
>(({ visible, isDisabled, nodeId, onDelete }, ref) => (
  <div
    ref={ref}
    className={cn(
      "absolute -top-4 left-1/2 transform -translate-x-1/2 flex items-center gap-0.5 bg-background border border-border rounded-md shadow-md p-0.5 transition-opacity duration-200 z-20 pointer-events-auto",
      visible ? "opacity-100" : "opacity-0 pointer-events-none",
    )}
  >
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button className="p-0.5 rounded-sm hover:bg-accent focus:outline-none focus:ring-1 focus:ring-primary focus:ring-offset-0.5">
            <Play className="h-2 w-2" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p>Run from this node</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button className="p-0.5 rounded-sm hover:bg-accent focus:outline-none focus:ring-1 focus:ring-primary focus:ring-offset-0.5">
            <Settings className="h-2 w-2" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p>Configure node</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button className="p-0.5 rounded-sm hover:bg-accent focus:outline-none focus:ring-1 focus:ring-primary focus:ring-offset-0.5">
            <ToggleLeft className="h-2 w-2" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{isDisabled ? "Enable" : "Disable"} node</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            className="p-0.5 rounded-sm hover:bg-accent hover:text-destructive focus:outline-none focus:ring-1 focus:ring-destructive focus:ring-offset-0.5"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onDelete?.(nodeId);
            }}
          >
            <Trash className="h-2 w-2" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p>Delete node</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  </div>
));

WorkflowNodeControls.displayName = "WorkflowNodeControls";
