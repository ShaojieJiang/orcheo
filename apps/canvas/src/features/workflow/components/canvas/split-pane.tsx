import React, { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";

interface SplitPaneProps {
  split: "vertical" | "horizontal";
  minSize?: number;
  defaultSize?: string | number;
  children: React.ReactNode[];
  className?: string;
  pane1Style?: React.CSSProperties;
  pane2Style?: React.CSSProperties;
  onChange?: (size: number) => void;
}

export default function SplitPane({
  split = "vertical",
  minSize = 100,
  defaultSize = "50%",
  children,
  className,
  pane1Style = {},
  pane2Style = {},
  onChange,
}: SplitPaneProps) {
  const isVertical = split === "vertical";
  const containerRef = useRef<HTMLDivElement>(null);
  const dividerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<string | number>(defaultSize);
  const [isDragging, setIsDragging] = useState(false);
  const [startPos, setStartPos] = useState(0);
  const [startSize, setStartSize] = useState(0);

  // Convert percentage to pixels
  const getPixelSize = (
    size: string | number,
    containerSize: number,
  ): number => {
    if (typeof size === "string" && size.endsWith("%")) {
      return (parseFloat(size) / 100) * containerSize;
    }
    return typeof size === "number" ? size : parseFloat(size);
  };

  // Convert pixels to CSS value (px or %)
  const getSizeStyle = (size: string | number): string => {
    if (typeof size === "string" && size.endsWith("%")) {
      return size;
    }
    return `${size}px`;
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    setStartPos(isVertical ? e.clientX : e.clientY);

    const containerRect = containerRef.current?.getBoundingClientRect();
    if (!containerRect) return;

    const containerSize = isVertical
      ? containerRect.width
      : containerRect.height;
    setStartSize(getPixelSize(size, containerSize));
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging || !containerRef.current) return;

    const containerRect = containerRef.current.getBoundingClientRect();
    const containerSize = isVertical
      ? containerRect.width
      : containerRect.height;
    const currentPos = isVertical ? e.clientX : e.clientY;
    const delta = currentPos - startPos;

    let newSize = Math.max(minSize, startSize + delta);
    newSize = Math.min(newSize, containerSize - minSize);

    setSize(newSize);

    if (onChange) {
      onChange(newSize);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    if (isDragging) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    } else {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDragging]);

  // Ensure we have exactly two children
  const [firstChild, secondChild] = React.Children.toArray(children).slice(
    0,
    2,
  );

  return (
    <div
      ref={containerRef}
      className={cn(
        "flex",
        isVertical ? "flex-row" : "flex-col",
        "relative",
        className,
      )}
      style={{
        cursor: isDragging
          ? isVertical
            ? "col-resize"
            : "row-resize"
          : "default",
        userSelect: isDragging ? "none" : "auto",
      }}
    >
      <div
        className="overflow-auto"
        style={{
          ...pane1Style,
          [isVertical ? "width" : "height"]: getSizeStyle(size),
          minWidth: isVertical ? minSize : undefined,
          minHeight: !isVertical ? minSize : undefined,
        }}
      >
        {firstChild}
      </div>

      <div
        ref={dividerRef}
        className={cn(
          "flex items-center justify-center",
          isVertical ? "cursor-col-resize" : "cursor-row-resize",
          isVertical
            ? "w-1 bg-border hover:bg-primary/50"
            : "h-1 bg-border hover:bg-primary/50",
        )}
        onMouseDown={handleMouseDown}
      />

      <div className="overflow-auto flex-1" style={pane2Style}>
        {secondChild}
      </div>
    </div>
  );
}
