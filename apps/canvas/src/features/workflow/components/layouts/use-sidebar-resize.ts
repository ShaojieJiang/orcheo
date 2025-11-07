import { useCallback, useEffect, useRef } from "react";

interface UseSidebarResizeProps {
  resizable: boolean;
  isCollapsed: boolean;
  sidebarWidth: number;
  minWidth: number;
  maxWidth: number;
  position: "left" | "right";
  onWidthChange?: (width: number) => void;
}

export const useSidebarResize = ({
  resizable,
  isCollapsed,
  sidebarWidth,
  minWidth,
  maxWidth,
  position,
  onWidthChange,
}: UseSidebarResizeProps) => {
  const resizingRef = useRef(false);
  const startXRef = useRef(0);
  const startWidthRef = useRef(sidebarWidth);

  useEffect(() => {
    startWidthRef.current = sidebarWidth;
  }, [sidebarWidth]);

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
      newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

      onWidthChange?.(newWidth);
    },
    [position, minWidth, maxWidth, onWidthChange],
  );

  const handleMouseUp = useCallback(() => {
    resizingRef.current = false;
  }, []);

  useEffect(() => {
    if (!resizable) {
      return;
    }

    const targetDocument =
      typeof document !== "undefined" ? document : undefined;
    if (!targetDocument) {
      return;
    }

    targetDocument.addEventListener("mousemove", handleMouseMove);
    targetDocument.addEventListener("mouseup", handleMouseUp);

    return () => {
      targetDocument.removeEventListener("mousemove", handleMouseMove);
      targetDocument.removeEventListener("mouseup", handleMouseUp);
    };
  }, [resizable, handleMouseMove, handleMouseUp]);

  return { handleMouseDown };
};
