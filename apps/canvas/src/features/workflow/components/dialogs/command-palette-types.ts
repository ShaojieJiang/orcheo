import type React from "react";

export interface CommandItem {
  id: string;
  name: string;
  description?: string;
  icon: React.ReactNode;
  type: "workflow" | "node" | "action" | "setting";
  shortcut?: string;
  href?: string;
}

export type CommandGroupMap = Record<CommandItem["type"], CommandItem[]>;
