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
  iconKey?: string;
  status?: NodeStatus;
  type?: string;
  backendType?: string;
  isDisabled?: boolean;
  onLabelChange?: (id: string, newLabel: string) => void;
  onNodeInspect?: (id: string) => void;
  onDelete?: (id: string) => void;
  isSearchMatch?: boolean;
  isSearchActive?: boolean;
  inputs?: NodeHandleConfig[];
  outputs?: NodeHandleConfig[];
  hideInputHandle?: boolean;
  [key: string]: unknown;
};

type NodeHandleConfig = {
  id?: string;
  label?: string;
  position?: "left" | "right" | "top" | "bottom";
};

const toHandlePosition = (
  value: NodeHandleConfig["position"],
  fallback: Position,
) => {
  switch (value) {
    case "left":
      return Position.Left;
    case "right":
      return Position.Right;
    case "top":
      return Position.Top;
    case "bottom":
      return Position.Bottom;
    default:
      return fallback;
  }
};

const WorkflowNode = ({ id, data, selected }: NodeProps<WorkflowNodeData>) => {
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
    python:
      "bg-orange-50 border-orange-200 dark:bg-orange-950/30 dark:border-orange-800/50",
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

  const inputHandles = nodeData.hideInputHandle
    ? []
    : nodeData.inputs && nodeData.inputs.length > 0
      ? nodeData.inputs
      : [{ id: undefined }];

  const outputHandles =
    nodeData.outputs && nodeData.outputs.length > 0
      ? nodeData.outputs
      : [{ id: undefined }];

  const renderHandle = (
    handle: NodeHandleConfig,
    index: number,
    total: number,
    type: "source" | "target",
  ) => {
    const fallbackPosition = type === "target" ? Position.Left : Position.Right;
    const position = toHandlePosition(handle.position, fallbackPosition);
    const percent = ((index + 1) / (total + 1)) * 100;
    const style: React.CSSProperties = {};

    // Only apply custom positioning if there are multiple handles
    if (total > 1) {
      if (position === Position.Left || position === Position.Right) {
        style.top = `${percent}%`;
      } else {
        style.left = `${percent}%`;
      }
    }

    return (
      <React.Fragment key={`${type}-${handle.id ?? index}`}>
        <Handle
          type={type}
          id={handle.id}
          position={position}
          className="!h-3 !w-3 !bg-primary !border-2 !border-background !z-10 !pointer-events-auto"
          style={style}
          isConnectable={true}
        />
        {type === "source" && handle.label && (
          <span
            className="absolute right-[-36px] text-[8px] uppercase tracking-wide text-muted-foreground pointer-events-none text-left"
            style={
              total > 1
                ? { top: `${percent}%`, transform: "translateY(-50%)" }
                : { top: "50%", transform: "translateY(-50%)" }
            }
          >
            {handle.label}
          </span>
        )}
      </React.Fragment>
    );
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
      <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-xs text-center whitespace-nowrap pointer-events-none">
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
      {inputHandles.map((handle, index) =>
        renderHandle(handle, index, inputHandles.length, "target"),
      )}

      {/* Output handle */}
      {outputHandles.map((handle, index) =>
        renderHandle(handle, index, outputHandles.length, "source"),
      )}

      {/* Node content */}
      <div className="h-full w-full flex items-center justify-center relative pointer-events-none">
        {/* Status indicator in corner */}
        <div className="absolute top-1 right-1 pointer-events-auto">
          {statusIcons[status]}
        </div>

        {/* Main icon */}
        <div className="flex items-center justify-center pointer-events-auto">
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
          "absolute -top-4 left-1/2 transform -translate-x-1/2 flex items-center gap-0.5 bg-background border border-border rounded-md shadow-md p-0.5 transition-opacity duration-200 z-20 pointer-events-auto",
          controlsVisible ? "opacity-100" : "opacity-0 pointer-events-none",
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
                  nodeData.onDelete?.(id);
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
    </div>
  );
};

export default WorkflowNode;
