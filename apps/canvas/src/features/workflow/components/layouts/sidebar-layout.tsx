import React, { useRef, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/design-system/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface SidebarLayoutProps {
  /**
   * Sidebar content
   */
  sidebar: React.ReactNode;

  /**
   * Main content area
   */
  children: React.ReactNode;

  /**
   * Whether the sidebar is collapsed
   */
  isCollapsed?: boolean;

  /**
   * Callback when sidebar collapse state changes
   */
  onToggleCollapse?: () => void;

  /**
   * Sidebar width when expanded (default: 300px)
   */
  sidebarWidth?: number;

  /**
   * Sidebar width when collapsed (default: 50px)
   */
  collapsedWidth?: number;

  /**
   * Whether the sidebar is resizable
   */
  resizable?: boolean;

  /**
   * Minimum sidebar width when resizing (default: 200px)
   */
  minWidth?: number;

  /**
   * Maximum sidebar width when resizing (default: 500px)
   */
  maxWidth?: number;

  /**
   * Callback when sidebar width changes
   */
  onWidthChange?: (width: number) => void;

  /**
   * Whether to show collapse button
   */
  showCollapseButton?: boolean;

  /**
   * Sidebar position
   */
  position?: "left" | "right";

  /**
   * Additional CSS classes for the container
   */
  className?: string;

  /**
   * Additional CSS classes for the sidebar
   */
  sidebarClassName?: string;

  /**
   * Additional CSS classes for the main content
   */
  mainClassName?: string;
}

/**
 * SidebarLayout - A reusable layout component with a collapsible, optionally
 * resizable sidebar and a main content area.
 *
 * This component provides:
 * - Collapsible sidebar with smooth transitions
 * - Optional resize handle for adjusting sidebar width
 * - Consistent styling across pages
 * - Support for left or right sidebar positioning
 * - Responsive behavior
 */
export default function SidebarLayout({
  sidebar,
  children,
  isCollapsed = false,
  onToggleCollapse,
  sidebarWidth = 300,
  collapsedWidth = 50,
  resizable = false,
  minWidth = 200,
  maxWidth = 500,
  onWidthChange,
  showCollapseButton = true,
  position = "left",
  className,
  sidebarClassName,
  mainClassName,
}: SidebarLayoutProps) {
  const resizingRef = useRef(false);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);
  const currentWidth = isCollapsed ? collapsedWidth : sidebarWidth;

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!resizable || isCollapsed) return;

      resizingRef.current = true;
      startXRef.current = e.clientX;
      startWidthRef.current = sidebarWidth;
      e.preventDefault();
    },
    [resizable, isCollapsed, sidebarWidth],
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!resizingRef.current) return;

      const delta =
        position === "left"
          ? e.clientX - startXRef.current
          : startXRef.current - e.clientX;
      let newWidth = startWidthRef.current + delta;

      // Clamp width within min/max bounds
      newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

      if (onWidthChange) {
        onWidthChange(newWidth);
      }
    },
    [position, minWidth, maxWidth, onWidthChange],
  );

  const handleMouseUp = useCallback(() => {
    resizingRef.current = false;
  }, []);

  useEffect(() => {
    if (resizable) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);

      return () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };
    }
  }, [resizable, handleMouseMove, handleMouseUp]);

  return (
    <div className={cn("flex h-full min-h-0", className)}>
      {position === "left" && (
        <>
          <aside
            className={cn(
              "relative h-full border-r border-border bg-card transition-all duration-300 flex flex-col",
              sidebarClassName,
            )}
            style={{ width: `${currentWidth}px` }}
          >
            {sidebar}

            {showCollapseButton && onToggleCollapse && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleCollapse}
                className="absolute top-3 right-3 z-10"
                title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                {isCollapsed ? (
                  <ChevronRight className="h-5 w-5" />
                ) : (
                  <ChevronLeft className="h-5 w-5" />
                )}
              </Button>
            )}

            {resizable && !isCollapsed && (
              <div
                className="absolute top-0 right-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/20 transition-colors"
                onMouseDown={handleMouseDown}
              />
            )}
          </aside>
          <main className={cn("flex-1 h-full min-h-0", mainClassName)}>
            {children}
          </main>
        </>
      )}

      {position === "right" && (
        <>
          <main className={cn("flex-1 h-full min-h-0", mainClassName)}>
            {children}
          </main>
          <aside
            className={cn(
              "relative h-full border-l border-border bg-card transition-all duration-300 flex flex-col",
              sidebarClassName,
            )}
            style={{ width: `${currentWidth}px` }}
          >
            {sidebar}

            {showCollapseButton && onToggleCollapse && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleCollapse}
                className="absolute top-3 left-3 z-10"
                title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                {isCollapsed ? (
                  <ChevronLeft className="h-5 w-5" />
                ) : (
                  <ChevronRight className="h-5 w-5" />
                )}
              </Button>
            )}

            {resizable && !isCollapsed && (
              <div
                className="absolute top-0 left-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/20 transition-colors"
                onMouseDown={handleMouseDown}
              />
            )}
          </aside>
        </>
      )}
    </div>
  );
}
