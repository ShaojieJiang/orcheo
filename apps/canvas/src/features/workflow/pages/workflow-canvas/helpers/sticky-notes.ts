import type {
  StickyNoteColor,
  StickyNoteNodeData,
} from "@features/workflow/components/nodes/sticky-note-node";

export const STICKY_NOTE_COLORS: StickyNoteColor[] = [
  "yellow",
  "pink",
  "blue",
  "green",
  "purple",
];

export const DEFAULT_STICKY_NOTE_COLOR: StickyNoteColor = "yellow";
export const DEFAULT_STICKY_NOTE_CONTENT =
  "Leave a note for collaborators";
export const STICKY_NOTE_MIN_WIDTH = 180;
export const STICKY_NOTE_MIN_HEIGHT = 150;
export const DEFAULT_STICKY_NOTE_WIDTH = 240;
export const DEFAULT_STICKY_NOTE_HEIGHT = 200;

export const isStickyNoteColor = (
  value: unknown,
): value is StickyNoteColor => {
  return (
    typeof value === "string" &&
    (STICKY_NOTE_COLORS as readonly string[]).includes(value)
  );
};

export const clampStickyDimension = (value: number, minimum: number) => {
  if (Number.isNaN(value) || !Number.isFinite(value)) {
    return minimum;
  }

  return Math.max(minimum, Math.round(value));
};

export const sanitizeStickyNoteDimension = (
  value: unknown,
  fallback: number,
  minimum: number,
) => {
  if (typeof value === "number") {
    return clampStickyDimension(value, minimum);
  }

  return clampStickyDimension(fallback, minimum);
};

export const sanitizeStickyNoteContent = (value: unknown) => {
  return typeof value === "string"
    ? value
    : DEFAULT_STICKY_NOTE_CONTENT;
};

export type { StickyNoteColor, StickyNoteNodeData };
