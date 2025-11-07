import React, { useState, useEffect } from "react";
import { Dialog, DialogContent } from "@/design-system/ui/dialog";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { Search, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import type { CommandItem } from "./command-palette-types";
import { COMMAND_ITEMS } from "./command-palette-items";
import {
  filterCommandItems,
  getTypeLabel,
  groupCommandItems,
} from "./command-palette-utils";
import { useCommandPaletteNavigation } from "./use-command-palette-navigation";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function CommandPalette({
  open,
  onOpenChange,
}: CommandPaletteProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Reset selection when opening or changing search
  useEffect(() => {
    setSelectedIndex(0);
  }, [open, searchQuery]);

  const filteredItems = React.useMemo(
    () => filterCommandItems(COMMAND_ITEMS, searchQuery),
    [searchQuery],
  );

  const groupedItems = React.useMemo(
    () => groupCommandItems(filteredItems),
    [filteredItems],
  );

  const groupedEntries = React.useMemo(
    () =>
      Object.entries(groupedItems) as Array<
        [CommandItem["type"], CommandItem[]]
      >,
    [groupedItems],
  );

  const handleSelect = (item: CommandItem) => {
    toast({
      title: item.name,
      description:
        item.type === "workflow"
          ? "Opening workflow in the canvas."
          : "This action will be wired up in a future iteration.",
    });
    onOpenChange(false);

    if (item.href) {
      window.location.href = item.href;
    }
  };

  useCommandPaletteNavigation({
    open,
    filteredItems,
    selectedIndex,
    setSelectedIndex,
    onSelect: handleSelect,
    onClose: () => onOpenChange(false),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px] p-0 gap-0 overflow-hidden">
        <div className="flex items-center border-b p-4">
          <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />

          <Input
            className="flex h-10 w-full rounded-md border-0 bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
            placeholder="Search for workflows, nodes, actions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
          />

          <kbd className="pointer-events-none ml-auto inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
            ESC
          </kbd>
        </div>

        <div className="max-h-[60vh] overflow-y-auto">
          {groupedEntries.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground">
              No results found
            </div>
          ) : (
            groupedEntries.map(([type, items]) => (
              <div key={type} className="px-2 py-3">
                <div className="px-2 mb-2 text-xs font-medium text-muted-foreground">
                  {getTypeLabel(type)}
                </div>
                <div className="space-y-1">
                  {items.map((item) => {
                    const itemIndex = filteredItems.findIndex(
                      (i) => i.id === item.id,
                    );
                    return (
                      <Button
                        key={item.id}
                        variant="ghost"
                        className={cn(
                          "w-full justify-start text-sm h-auto py-2",
                          selectedIndex === itemIndex && "bg-accent",
                        )}
                        onClick={() => handleSelect(item)}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                      >
                        <div className="flex items-center w-full">
                          <div className="flex items-center gap-2 flex-1">
                            <div className="flex-shrink-0 text-muted-foreground">
                              {item.icon}
                            </div>
                            <div className="flex flex-col items-start">
                              <span>{item.name}</span>
                              {item.description && (
                                <span className="text-xs text-muted-foreground">
                                  {item.description}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {item.type === "workflow" && (
                              <Badge variant="outline" className="ml-auto">
                                Workflow
                              </Badge>
                            )}
                            {item.type === "node" && (
                              <Badge variant="outline" className="ml-auto">
                                Node
                              </Badge>
                            )}
                            {item.shortcut && (
                              <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                                {item.shortcut}
                              </kbd>
                            )}
                            {item.href && (
                              <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            )}
                          </div>
                        </div>
                      </Button>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="border-t p-2 text-xs text-muted-foreground">
          <div className="flex gap-4 justify-center">
            <div className="flex items-center gap-1">
              <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                ↑
              </kbd>
              <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                ↓
              </kbd>
              <span>Navigate</span>
            </div>
            <div className="flex items-center gap-1">
              <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                Enter
              </kbd>
              <span>Select</span>
            </div>
            <div className="flex items-center gap-1">
              <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                Esc
              </kbd>
              <span>Close</span>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
