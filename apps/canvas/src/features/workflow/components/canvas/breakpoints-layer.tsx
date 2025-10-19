import React, { useState } from "react";
import { Button } from "@/design-system/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { cn } from "@/lib/utils";
import { Bug, X } from "lucide-react";

interface Breakpoint {
  id: string;
  nodeId: string;
  position: { x: number; y: number };
  enabled: boolean;
}

interface BreakpointsLayerProps {
  breakpoints?: Breakpoint[];
  onAddBreakpoint?: (
    nodeId: string,
    position: { x: number; y: number },
  ) => void;
  onToggleBreakpoint?: (id: string) => void;
  onRemoveBreakpoint?: (id: string) => void;
  debugMode?: boolean;
  className?: string;
}

export default function BreakpointsLayer({
  breakpoints = [],
  onAddBreakpoint,
  onToggleBreakpoint,
  onRemoveBreakpoint,
  debugMode = false,
  className,
}: BreakpointsLayerProps) {
  const [isAddingBreakpoint, setIsAddingBreakpoint] = useState(false);

  const handleToggleDebugMode = () => {
    setIsAddingBreakpoint(!isAddingBreakpoint);
  };

  return (
    <div className={cn("absolute inset-0 pointer-events-none", className)}>
      {/* Debug mode toggle button */}
      <div className="absolute top-4 left-4 pointer-events-auto z-10">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={debugMode ? "default" : "outline"}
                size="sm"
                onClick={handleToggleDebugMode}
                className="gap-2"
              >
                {isAddingBreakpoint ? (
                  <>
                    <X className="h-4 w-4" />
                    Cancel
                  </>
                ) : (
                  <>
                    <Bug className="h-4 w-4" />

                    {debugMode ? "Debug Mode" : "Add Breakpoint"}
                  </>
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {isAddingBreakpoint
                ? "Cancel adding breakpoint"
                : debugMode
                  ? "Currently in debug mode"
                  : "Add breakpoints to pause workflow execution"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      {/* Instructions when adding breakpoint */}
      {isAddingBreakpoint && (
        <div className="absolute top-16 left-4 bg-background border border-border rounded-md p-2 shadow-md pointer-events-auto">
          <p className="text-xs text-muted-foreground">
            Click on a node to add a breakpoint
          </p>
        </div>
      )}

      {/* Existing breakpoints */}
      {breakpoints.map((breakpoint) => (
        <div
          key={breakpoint.id}
          className="absolute pointer-events-auto"
          style={{
            left: `${breakpoint.position.x}px`,
            top: `${breakpoint.position.y}px`,
            transform: "translate(-50%, -50%)",
          }}
        >
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className={cn(
                    "h-5 w-5 rounded-full p-0 border-2",
                    breakpoint.enabled
                      ? "bg-red-500 border-red-500 hover:bg-red-600 hover:border-red-600"
                      : "bg-muted border-muted-foreground hover:bg-muted hover:border-foreground",
                  )}
                  onClick={() => onToggleBreakpoint?.(breakpoint.id)}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    onRemoveBreakpoint?.(breakpoint.id);
                  }}
                >
                  <span className="sr-only">
                    {breakpoint.enabled ? "Disable" : "Enable"} breakpoint
                  </span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <div className="text-xs">
                  <p>
                    {breakpoint.enabled
                      ? "Breakpoint active"
                      : "Breakpoint disabled"}
                  </p>
                  <p className="text-muted-foreground">
                    Click to {breakpoint.enabled ? "disable" : "enable"},
                    right-click to remove
                  </p>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      ))}

      {/* Debug execution status */}
      {debugMode && (
        <div className="absolute bottom-4 left-4 bg-background border border-border rounded-md p-2 shadow-md pointer-events-auto flex items-center gap-2">
          <div className="h-3 w-3 rounded-full bg-amber-500 animate-pulse"></div>
          <span className="text-xs font-medium">Debug Mode Active</span>
        </div>
      )}
    </div>
  );
}
