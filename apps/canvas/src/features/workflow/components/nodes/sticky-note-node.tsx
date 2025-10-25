import React, { useCallback, useMemo, useRef } from "react";
import { NodeProps } from "@xyflow/react";
import { Palette, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/design-system/ui/button";
import { Textarea } from "@/design-system/ui/textarea";

export type StickyNoteColor = "yellow" | "pink" | "blue" | "green" | "purple";

export interface StickyNoteNodeData {
  label?: string;
  color?: StickyNoteColor;
  content?: string;
  width?: number;
  height?: number;
  onUpdateStickyNote?: (
    id: string,
    updates: Partial<
      Pick<StickyNoteNodeData, "color" | "content" | "width" | "height">
    >,
  ) => void;
  onDelete?: (id: string) => void;
}

const NOTE_COLORS: Record<StickyNoteColor, string> = {
  yellow:
    "bg-amber-100 border-amber-200 text-amber-950 dark:bg-amber-500/20 dark:border-amber-400/30 dark:text-amber-100",
  pink: "bg-rose-100 border-rose-200 text-rose-950 dark:bg-rose-500/20 dark:border-rose-400/30 dark:text-rose-100",
  blue: "bg-sky-100 border-sky-200 text-sky-950 dark:bg-sky-500/20 dark:border-sky-400/30 dark:text-sky-100",
  green:
    "bg-emerald-100 border-emerald-200 text-emerald-950 dark:bg-emerald-500/20 dark:border-emerald-400/30 dark:text-emerald-100",
  purple:
    "bg-violet-100 border-violet-200 text-violet-950 dark:bg-violet-500/20 dark:border-violet-400/30 dark:text-violet-100",
};

const COLOR_OPTIONS: StickyNoteColor[] = [
  "yellow",
  "pink",
  "blue",
  "green",
  "purple",
];

const MIN_WIDTH = 180;
const MIN_HEIGHT = 150;

const isStickyNoteColor = (value: unknown): value is StickyNoteColor => {
  return (
    typeof value === "string" &&
    (COLOR_OPTIONS as readonly string[]).includes(value)
  );
};

const clampDimension = (value: number, minimum: number) => {
  if (Number.isNaN(value) || !Number.isFinite(value)) {
    return minimum;
  }
  return Math.max(minimum, Math.round(value));
};

const StickyNoteNode: React.FC<NodeProps<StickyNoteNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const pointerStateRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
  } | null>(null);

  const color = useMemo<StickyNoteColor>(() => {
    return isStickyNoteColor(data.color) ? data.color : "yellow";
  }, [data.color]);

  const width = clampDimension(
    typeof data.width === "number" ? data.width : MIN_WIDTH,
    MIN_WIDTH,
  );
  const height = clampDimension(
    typeof data.height === "number" ? data.height : MIN_HEIGHT,
    MIN_HEIGHT,
  );
  const label = data.label?.length ? data.label : "Sticky Note";

  const handleColorChange = useCallback(
    (nextColor: StickyNoteColor) => {
      if (data.onUpdateStickyNote) {
        data.onUpdateStickyNote(id, { color: nextColor });
      }
    },
    [data, id],
  );

  const handleContentChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      if (data.onUpdateStickyNote) {
        data.onUpdateStickyNote(id, { content: event.target.value });
      }
    },
    [data, id],
  );

  const stopPropagation = (event: React.SyntheticEvent) => {
    event.stopPropagation();
  };

  const handleDelete = useCallback(
    (event: React.MouseEvent) => {
      event.stopPropagation();
      data.onDelete?.(id);
    },
    [data, id],
  );

  const handleResizePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      event.stopPropagation();
      event.preventDefault();
      pointerStateRef.current = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        startWidth: width,
        startHeight: height,
      };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [height, width],
  );

  const handleResizePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const state = pointerStateRef.current;
      if (
        !state ||
        state.pointerId !== event.pointerId ||
        !data.onUpdateStickyNote
      ) {
        return;
      }

      const deltaX = event.clientX - state.startX;
      const deltaY = event.clientY - state.startY;
      const nextWidth = clampDimension(state.startWidth + deltaX, MIN_WIDTH);
      const nextHeight = clampDimension(state.startHeight + deltaY, MIN_HEIGHT);

      data.onUpdateStickyNote(id, {
        width: nextWidth,
        height: nextHeight,
      });
    },
    [data, id],
  );

  const handleResizePointerUp = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const state = pointerStateRef.current;
      if (!state || state.pointerId !== event.pointerId) {
        return;
      }

      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
      pointerStateRef.current = null;
    },
    [],
  );

  const colorClasses = NOTE_COLORS[color] ?? NOTE_COLORS.yellow;
  const content = typeof data.content === "string" ? data.content : "";

  return (
    <div
      className={cn(
        "group relative flex h-full w-full min-h-[150px] min-w-[180px] flex-col rounded-xl border shadow-md transition",
        colorClasses,
        selected && "ring-2 ring-primary ring-offset-2",
      )}
      style={{ width, height }}
      onClick={stopPropagation}
    >
      <div className="flex items-center justify-between px-3 py-2 text-xs font-medium">
        <div className="flex items-center gap-1 text-muted-foreground">
          <Palette className="h-3 w-3" />
          {label}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-destructive"
          onClick={handleDelete}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>

      <Textarea
        value={content}
        onChange={handleContentChange}
        placeholder="Leave a note for collaborators"
        className="flex-1 resize-none border-none bg-transparent px-3 text-sm focus-visible:ring-0 focus-visible:ring-offset-0"
        onPointerDown={(event) => event.stopPropagation()}
      />

      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="flex items-center gap-1">
          {COLOR_OPTIONS.map((colorOption) => (
            <button
              key={colorOption}
              type="button"
              className={cn(
                "h-4 w-4 rounded-full border transition hover:scale-110",
                NOTE_COLORS[colorOption],
                colorOption === color && "ring-2 ring-offset-1 ring-primary",
              )}
              onClick={(event) => {
                event.stopPropagation();
                handleColorChange(colorOption);
              }}
              aria-label={`Set sticky note color to ${colorOption}`}
            />
          ))}
        </div>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Drag to move • Resize corner
        </span>
      </div>

      <div
        role="presentation"
        className="absolute bottom-1 right-1 h-3 w-3 cursor-se-resize rounded-sm border border-dashed border-border/60 bg-transparent"
        onPointerDown={handleResizePointerDown}
        onPointerMove={handleResizePointerMove}
        onPointerUp={handleResizePointerUp}
        onPointerCancel={handleResizePointerUp}
      />
    </div>
  );
};

export default StickyNoteNode;
