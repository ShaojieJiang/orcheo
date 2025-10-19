import React, { useEffect, useRef } from "react";
import { Button } from "@/design-system/ui/button";
import { cn } from "@/lib/utils";
import { Maximize, Minimize } from "lucide-react";

interface MiniMapProps {
  flowInstance?: Record<string, unknown>;
  expanded?: boolean;
  onToggleExpand?: () => void;
  className?: string;
}

export default function MiniMap({
  flowInstance,
  expanded = false,
  onToggleExpand,
  className,
}: MiniMapProps) {
  const miniMapRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // This is a simplified version - in a real implementation, you would
  // use the actual ReactFlow MiniMap component or create a custom implementation
  // that renders a scaled-down version of the workflow
  useEffect(() => {
    if (!miniMapRef.current || !flowInstance) return;

    // In a real implementation, you would:
    // 1. Get the nodes and edges from flowInstance
    // 2. Calculate the viewport bounds
    // 3. Render a scaled-down version of the workflow
    // 4. Add interaction for panning the main viewport

    // For this demo, we'll just render a placeholder
  }, [flowInstance]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "absolute bottom-4 right-4 bg-background border border-border rounded-md shadow-md transition-all duration-300 overflow-hidden",
        expanded ? "w-64 h-48" : "w-32 h-24",
        className,
      )}
    >
      <div className="absolute top-2 right-2 z-10">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 bg-background/80 backdrop-blur-sm"
          onClick={onToggleExpand}
        >
          {expanded ? (
            <Minimize className="h-3 w-3" />
          ) : (
            <Maximize className="h-3 w-3" />
          )}
        </Button>
      </div>

      <div
        ref={miniMapRef}
        className="w-full h-full bg-muted/20 relative"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(0,0,0,0.05) 1px, transparent 1px)",
          backgroundSize: "10px 10px",
        }}
      >
        {/* Placeholder nodes for demonstration */}
        <div className="absolute top-1/4 left-1/4 w-4 h-4 bg-blue-500/70 rounded-sm"></div>
        <div className="absolute top-1/3 left-1/2 w-4 h-4 bg-purple-500/70 rounded-sm"></div>
        <div className="absolute top-1/2 left-1/3 w-4 h-4 bg-amber-500/70 rounded-sm"></div>
        <div className="absolute top-2/3 left-2/3 w-4 h-4 bg-green-500/70 rounded-sm"></div>

        {/* Placeholder edges */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <line
            x1="25%"
            y1="25%"
            x2="50%"
            y2="33%"
            stroke="rgba(0,0,0,0.2)"
            strokeWidth="1"
          />

          <line
            x1="50%"
            y1="33%"
            x2="33%"
            y2="50%"
            stroke="rgba(0,0,0,0.2)"
            strokeWidth="1"
          />

          <line
            x1="33%"
            y1="50%"
            x2="67%"
            y2="67%"
            stroke="rgba(0,0,0,0.2)"
            strokeWidth="1"
          />
        </svg>

        {/* Viewport indicator */}
        <div className="absolute border-2 border-primary/50 bg-primary/10 w-1/2 h-1/2 left-1/4 top-1/4"></div>
      </div>
    </div>
  );
}
