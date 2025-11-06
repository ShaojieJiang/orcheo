import type { StickyNoteColor } from "@features/workflow/components/nodes/sticky-note-node";

export const defaultNodeStyle = {
  background: "none",
  border: "none",
  padding: 0,
  borderRadius: 0,
  width: "auto",
  boxShadow: "none",
} as const;

export const STICKY_NOTE_COLORS: StickyNoteColor[] = [
  "yellow",
  "pink",
  "blue",
  "green",
  "purple",
];

export const DEFAULT_STICKY_NOTE_COLOR: StickyNoteColor = "yellow";
export const DEFAULT_STICKY_NOTE_CONTENT = "Leave a note for collaborators";
export const STICKY_NOTE_MIN_WIDTH = 180;
export const STICKY_NOTE_MIN_HEIGHT = 150;
export const DEFAULT_STICKY_NOTE_WIDTH = 240;
export const DEFAULT_STICKY_NOTE_HEIGHT = 200;

export const isStickyNoteColor = (value: unknown): value is StickyNoteColor => {
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
  return typeof value === "string" ? value : DEFAULT_STICKY_NOTE_CONTENT;
};

export const generateRandomId = (prefix: string) => {
  if (
    typeof globalThis.crypto !== "undefined" &&
    "randomUUID" in globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return `${prefix}-${globalThis.crypto.randomUUID()}`;
  }

  const timestamp = Date.now().toString(36);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `${prefix}-${timestamp}-${randomSuffix}`;
};

export const generateNodeId = () => generateRandomId("node");
