import { useEffect } from "react";
import type React from "react";
import type { CommandItem } from "./command-palette-types";

interface NavigationOptions {
  open: boolean;
  filteredItems: CommandItem[];
  selectedIndex: number;
  setSelectedIndex: React.Dispatch<React.SetStateAction<number>>;
  onSelect: (item: CommandItem) => void;
  onClose: () => void;
}

export const useCommandPaletteNavigation = ({
  open,
  filteredItems,
  selectedIndex,
  setSelectedIndex,
  onSelect,
  onClose,
}: NavigationOptions) => {
  useEffect(() => {
    const targetWindow = typeof window !== "undefined" ? window : undefined;
    if (!targetWindow) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!open) return;

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setSelectedIndex((prev) =>
            Math.min(prev + 1, filteredItems.length - 1),
          );
          break;
        case "ArrowUp":
          event.preventDefault();
          setSelectedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case "Enter":
          event.preventDefault();
          if (filteredItems[selectedIndex]) {
            onSelect(filteredItems[selectedIndex]);
          }
          break;
        case "Escape":
          event.preventDefault();
          onClose();
          break;
        default:
          break;
      }
    };

    targetWindow.addEventListener("keydown", handleKeyDown);
    return () => targetWindow.removeEventListener("keydown", handleKeyDown);
  }, [filteredItems, onClose, onSelect, open, selectedIndex, setSelectedIndex]);
};
