import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Play, Square } from "lucide-react";
import { NodeProps, Handle, Position } from "@xyflow/react";
import NodeLabel from "@features/workflow/components/nodes/node-label";

export type StartEndNodeData = {
  label: string;
  type: "start" | "end";
  description?: string;
  onLabelChange?: (id: string, newLabel: string) => void;
  [key: string]: unknown;
};

const StartEndNode = ({ data, selected, id }: NodeProps) => {
  const nodeData = data as StartEndNodeData;
  const { label, type, onLabelChange } = nodeData;
  const [isHovered, setIsHovered] = useState(false);

  const nodeColors = {
    start:
      "bg-emerald-50 border-emerald-300 dark:bg-emerald-950/30 dark:border-emerald-800/50",
    end: "bg-rose-50 border-rose-300 dark:bg-rose-950/30 dark:border-rose-800/50",
  } as const;

  return (
    <div className="flex flex-col items-center">
      {/* Node label component */}
      <NodeLabel id={id} label={label} onLabelChange={onLabelChange} />

      <div
        className={cn(
          "group relative rounded-xl border-2 shadow-sm transition-all duration-200 h-16 w-16 aspect-square flex items-center justify-center",
          nodeColors[type],
          selected && "ring-2 ring-primary ring-offset-2",
        )}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Only show input handle on end node */}
        {type === "end" && (
          <Handle
            type="target"
            position={Position.Left}
            className="!h-3 !w-3 !bg-primary !border-2 !border-background"
          />
        )}

        {/* Only show output handle on start node */}
        {type === "start" && (
          <Handle
            type="source"
            position={Position.Right}
            className="!h-3 !w-3 !bg-primary !border-2 !border-background"
          />
        )}

        {/* Node icon */}
        <div className="flex items-center justify-center">
          {type === "start" ? (
            <Play className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
          ) : (
            <Square className="h-5 w-5 text-rose-600 dark:text-rose-400" />
          )}
        </div>

        {/* Tooltip for node name */}
        {isHovered && (
          <div className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 bg-background border border-border rounded-md shadow-md p-1 text-xs">
            {label}
          </div>
        )}
      </div>
    </div>
  );
};

export default StartEndNode;
