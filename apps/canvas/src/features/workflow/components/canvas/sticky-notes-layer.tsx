import React, { useCallback, useRef } from "react";
import { Trash2, Palette } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/design-system/ui/button";
import { Textarea } from "@/design-system/ui/textarea";

export type StickyNoteColor = "yellow" | "pink" | "blue" | "green" | "purple";

export interface StickyNote {
  id: string;
  x: number;
  y: number;
  content: string;
  color: StickyNoteColor;
}

interface StickyNotesLayerProps {
  notes: StickyNote[];
  onUpdateNote?: (id: string, updates: Partial<StickyNote>) => void;
  onDeleteNote?: (id: string) => void;
  className?: string;
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

const StickyNotesLayer: React.FC<StickyNotesLayerProps> = ({
  notes,
  onUpdateNote,
  onDeleteNote,
  className,
}) => {
  const draggingIdRef = useRef<string | null>(null);
  const dragStartRef = useRef<{
    x: number;
    y: number;
    originX: number;
    originY: number;
  } | null>(null);

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>, note: StickyNote) => {
      if (event.button !== 0) {
        return;
      }
      draggingIdRef.current = note.id;
      dragStartRef.current = {
        x: event.clientX,
        y: event.clientY,
        originX: note.x,
        originY: note.y,
      };
      (event.target as HTMLElement).setPointerCapture(event.pointerId);
    },
    [],
  );

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const activeId = draggingIdRef.current;
      const dragStart = dragStartRef.current;
      if (!activeId || !dragStart) {
        return;
      }

      const deltaX = event.clientX - dragStart.x;
      const deltaY = event.clientY - dragStart.y;
      onUpdateNote?.(activeId, {
        x: dragStart.originX + deltaX,
        y: dragStart.originY + deltaY,
      });
    },
    [onUpdateNote],
  );

  const handlePointerUp = useCallback(
    (event?: React.PointerEvent<HTMLDivElement>) => {
      if (event && event.currentTarget?.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
      draggingIdRef.current = null;
      dragStartRef.current = null;
    },
    [],
  );

  const handleContentChange = useCallback(
    (id: string, value: string) => {
      onUpdateNote?.(id, { content: value });
    },
    [onUpdateNote],
  );

  const handleColorChange = useCallback(
    (id: string, color: StickyNoteColor) => {
      onUpdateNote?.(id, { color });
    },
    [onUpdateNote],
  );

  return (
    <div className={cn("absolute inset-0 pointer-events-none", className)}>
      {notes.map((note) => {
        const colorClasses = NOTE_COLORS[note.color] ?? NOTE_COLORS.yellow;
        return (
          <div
            key={note.id}
            role="note"
            className={cn(
              "absolute w-56 min-h-[160px] rounded-lg border shadow-md pointer-events-auto flex flex-col",
              colorClasses,
            )}
            style={{
              left: `${note.x}px`,
              top: `${note.y}px`,
            }}
            onPointerDown={(event) => handlePointerDown(event, note)}
            onPointerMove={handlePointerMove}
            onPointerUp={(event) => handlePointerUp(event)}
            onPointerCancel={(event) => handlePointerUp(event)}
          >
            <div className="flex items-center justify-between px-3 py-2 text-xs font-medium">
              <div className="flex items-center gap-1 text-muted-foreground">
                <Palette className="h-3 w-3" />
                Sticky Note
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-destructive"
                onClick={(event) => {
                  event.stopPropagation();
                  onDeleteNote?.(note.id);
                }}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>

            <Textarea
              value={note.content}
              onChange={(event) =>
                handleContentChange(note.id, event.target.value)
              }
              placeholder="Leave a note for collaborators"
              className="flex-1 bg-transparent border-none resize-none focus-visible:ring-0 focus-visible:ring-offset-0 px-3"
            />

            <div className="flex items-center justify-between px-3 py-2 gap-2">
              <div className="flex items-center gap-1">
                {COLOR_OPTIONS.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className={cn(
                      "h-4 w-4 rounded-full border transition hover:scale-110",
                      NOTE_COLORS[color],
                      color === note.color &&
                        "ring-2 ring-offset-1 ring-primary",
                    )}
                    onClick={(event) => {
                      event.stopPropagation();
                      handleColorChange(note.id, color);
                    }}
                    aria-label={`Set sticky note color to ${color}`}
                  />
                ))}
              </div>
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Drag to reposition
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default StickyNotesLayer;
