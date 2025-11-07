import React from "react";
import { Handle, Position } from "@xyflow/react";

import type { NodeHandleConfig } from "./workflow-node.types";

const toHandlePosition = (
  value: NodeHandleConfig["position"],
  fallback: Position,
): Position => {
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

const renderHandle = (
  handle: NodeHandleConfig,
  index: number,
  total: number,
  type: "source" | "target",
) => {
  const fallback = type === "target" ? Position.Left : Position.Right;
  const position = toHandlePosition(handle.position, fallback);
  const percent = ((index + 1) / (total + 1)) * 100;
  const style: React.CSSProperties = {};

  if (total > 1) {
    if (position === Position.Left || position === Position.Right) {
      style.top = `${percent}%`;
    } else {
      style.left = `${percent}%`;
    }
  }

  const labelStyle =
    total > 1
      ? { top: `${percent}%`, transform: "translateY(-50%)" }
      : { top: "50%", transform: "translateY(-50%)" };

  return (
    <React.Fragment key={`${type}-${handle.id ?? index}`}>
      <Handle
        type={type}
        id={handle.id}
        position={position}
        className="!h-2 !w-2 !bg-primary !border-2 !border-background !z-10 !pointer-events-auto"
        style={style}
        isConnectable
      />
      {type === "source" && handle.label && (
        <span
          className="absolute left-[calc(100%+8px)] text-[6px] uppercase tracking-wide text-muted-foreground pointer-events-none whitespace-nowrap"
          style={labelStyle}
        >
          {handle.label}
        </span>
      )}
    </React.Fragment>
  );
};

export const WorkflowNodeHandles = ({
  handles,
  type,
}: {
  handles: NodeHandleConfig[];
  type: "source" | "target";
}) =>
  handles.map((handle, index) =>
    renderHandle(handle, index, handles.length, type),
  );
