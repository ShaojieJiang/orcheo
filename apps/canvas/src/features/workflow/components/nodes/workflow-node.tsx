import React, { useState, useRef, useEffect } from "react";
import {
  CheckCircle,
  Clock,
  AlertCircle,
  Play,
  Settings,
  Trash,
  ToggleLeft,
} from "lucide-react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";

export type NodeStatus = "idle" | "running" | "success" | "error";

export type WorkflowNodeData = {
  label: string;
  description?: string;
  icon?: React.ReactNode;
  status?: NodeStatus;
  type?: string;
  isDisabled?: boolean;
  onLabelChange?: (id: string, newLabel: string) => void;
  onNodeInspect?: (id: string) => void;
  isSearchMatch?: boolean;
  isSearchActive?: boolean;
  [key: string]: unknown;
};

const WorkflowNode = ({ data, selected }: NodeProps) => {
  const nodeData = data as WorkflowNodeData;
  const [controlsVisible, setControlsVisible] = useState(false);
  const controlsRef = useRef<HTMLDivElement>(null);
  const nodeRef = useRef<HTMLDivElement>(null);

  const {
    label,
    icon,
    status = "idle" as const,
    type,
    isDisabled,
    isSearchMatch = false,
    isSearchActive = false,
  } = nodeData;

  // Handle clicks outside the controls to hide them
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (
        controlsRef.current &&
        !controlsRef.current.contains(target) &&
        nodeRef.current &&
        !nodeRef.current.contains(target)
      ) {
        setControlsVisible(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const statusIcons = {
    idle: <Clock className="h-4 w-4 text-muted-foreground" />,
    running: <Clock className="h-4 w-4 text-blue-500 animate-pulse" />,
    success: <CheckCircle className="h-4 w-4 text-green-500" />,
    error: <AlertCircle className="h-4 w-4 text-red-500" />,
  } as const;

  const nodeColors = {
    default: "bg-card border-border",
    api: "bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-800/50",
    function:
      "bg-purple-50 border-purple-200 dark:bg-purple-950/30 dark:border-purple-800/50",
    trigger:
      "bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-800/50",
    data: "bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800/50",
    ai: "bg-indigo-50 border-indigo-200 dark:bg-indigo-950/30 dark:border-indigo-800/50",
    subWorkflow:
      "bg-slate-50 border-slate-200 dark:bg-slate-900/40 dark:border-slate-700/60",
  } as const;

  const nodeColor =
    type && type in nodeColors
      ? nodeColors[type as keyof typeof nodeColors]
      : nodeColors.default;

  const handleMouseEnter = () => {
    setControlsVisible(true);
  };

  const handleMouseLeave = () => {
    setControlsVisible(false);
  };

  return (
    <div
      ref={nodeRef}
      data-search-match={isSearchMatch ? "true" : undefined}
      data-search-active={isSearchActive ? "true" : undefined}
      className={cn(
        "group relative border shadow-sm transition-all duration-200",
        nodeColor,
        selected && "ring-2 ring-primary ring-offset-2",
        isSearchMatch &&
          !isSearchActive &&
          "ring-2 ring-sky-400/70 ring-offset-2",
        isSearchActive && "ring-4 ring-sky-500 ring-offset-2",
        isDisabled && "opacity-60",
        "h-16 w-16 rounded-xl cursor-pointer",
      )}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      tabIndex={0}
      role="button"
      aria-selected={Boolean(selected)}
    >
      {/* Simple text label */}
      <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-xs text-center whitespace-nowrap">
        <span
          className={cn(
            "px-2 py-0.5 rounded-full transition-colors",
            isSearchActive
              ? "bg-sky-500/10 text-sky-700 dark:text-sky-300"
              : isSearchMatch
                ? "bg-sky-500/5 text-sky-600 dark:text-sky-200"
                : undefined,
          )}
        >
          {label}
        </span>
      </div>

      {/* Input handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!h-3 !w-3 !bg-primary !border-2 !border-background"
      />

      {/* Output handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="!h-3 !w-3 !bg-primary !border-2 !border-background"
      />

      {/* Node content */}
      <div className="h-full w-full flex items-center justify-center relative">
        {/* Status indicator in corner */}
        <div className="absolute top-1 right-1">{statusIcons[status]}</div>

        {/* Main icon */}
        <div className="flex items-center justify-center">
          {icon ? (
            <div className="scale-125">{icon}</div>
          ) : (
            <div className="text-xs font-medium text-center">
              {label.substring(0, 2)}
            </div>
          )}
        </div>
      </div>

      {/* Hover actions */}
      <div
        ref={controlsRef}
        className={cn(
          "absolute -top-10 left-1/2 transform -translate-x-1/2 flex items-center gap-1 bg-background border border-border rounded-md shadow-md p-1 transition-opacity duration-200 z-20",
          controlsVisible ? "opacity-100" : "opacity-0 pointer-events-none",
        )}
      >
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="p-1.5 rounded-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1">
                <Play className="h-4 w-4" />
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
              <button className="p-1.5 rounded-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1">
                <Settings className="h-4 w-4" />
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
              <button className="p-1.5 rounded-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1">
                <ToggleLeft className="h-4 w-4" />
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
              <button className="p-1.5 rounded-sm hover:bg-accent hover:text-destructive focus:outline-none focus:ring-2 focus:ring-destructive focus:ring-offset-1">
                <Trash className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Delete node</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  );
};

export default WorkflowNode;
