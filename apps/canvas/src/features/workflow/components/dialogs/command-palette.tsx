import React, { useState, useEffect } from "react";
import { Dialog, DialogContent } from "@/design-system/ui/dialog";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import {
  Search,
  Folder,
  FileText,
  Code,
  Settings,
  Zap,
  Database,
  Sparkles,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface CommandItem {
  id: string;
  name: string;
  description?: string;
  icon: React.ReactNode;
  type: "workflow" | "node" | "action" | "setting";
  shortcut?: string;
  href?: string;
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

  // Handle keyboard navigation
  useEffect(() => {
    const targetWindow = typeof window !== "undefined" ? window : undefined;
    if (!targetWindow) {
      return;
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (!open) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((prevIndex) =>
            Math.min(prevIndex + 1, filteredItems.length - 1),
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((prevIndex) => Math.max(prevIndex - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (filteredItems[selectedIndex]) {
            handleSelect(filteredItems[selectedIndex]);
          }
          break;
        case "Escape":
          e.preventDefault();
          onOpenChange(false);
          break;
      }
    };

    targetWindow.addEventListener("keydown", handleKeyDown);
    return () => targetWindow.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, selectedIndex, onOpenChange]);

  // Sample command items
  const commandItems: CommandItem[] = [
    {
      id: "workflow-1",
      name: "Customer Onboarding",
      description: "Automated customer onboarding workflow",
      icon: <Folder className="h-4 w-4" />,

      type: "workflow",
      href: "/workflow-canvas",
    },
    {
      id: "workflow-2",
      name: "Email Campaign",
      description: "Marketing email sequence",
      icon: <Folder className="h-4 w-4" />,

      type: "workflow",
      href: "/workflow-canvas",
    },
    {
      id: "node-1",
      name: "HTTP Request",
      description: "Make HTTP requests to external APIs",
      icon: <Code className="h-4 w-4" />,

      type: "node",
    },
    {
      id: "node-2",
      name: "Transform Data",
      description: "Process and transform data",
      icon: <Code className="h-4 w-4" />,

      type: "node",
    },
    {
      id: "node-3",
      name: "Database Query",
      description: "Execute SQL queries",
      icon: <Database className="h-4 w-4" />,

      type: "node",
    },
    {
      id: "node-4",
      name: "AI Text Generation",
      description: "Generate text using AI models",
      icon: <Sparkles className="h-4 w-4" />,

      type: "node",
    },
    {
      id: "action-1",
      name: "Create New Workflow",
      icon: <FileText className="h-4 w-4" />,

      type: "action",
    },
    {
      id: "action-2",
      name: "Run Current Workflow",
      icon: <Zap className="h-4 w-4" />,

      type: "action",
      shortcut: "⌘R",
    },
    {
      id: "setting-1",
      name: "User Settings",
      icon: <Settings className="h-4 w-4" />,

      type: "setting",
      href: "/settings",
    },
  ];

  // Filter items based on search query
  const filteredItems = searchQuery
    ? commandItems.filter(
        (item) =>
          item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (item.description &&
            item.description.toLowerCase().includes(searchQuery.toLowerCase())),
      )
    : commandItems;

  // Group items by type
  const groupedItems = filteredItems.reduce(
    (acc, item) => {
      if (!acc[item.type]) {
        acc[item.type] = [];
      }
      acc[item.type].push(item);
      return acc;
    },
    {} as Record<string, CommandItem[]>,
  );

  const handleSelect = (item: CommandItem) => {
    // Handle selection based on item type
    toast({
      title: item.name,
      description:
        item.type === "workflow"
          ? "Opening workflow in the canvas."
          : "This action will be wired up in a future iteration.",
    });
    onOpenChange(false);

    // In a real implementation, you would navigate or perform the action
    if (item.href) {
      // Navigate to the URL
      window.location.href = item.href;
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case "workflow":
        return "Workflows";
      case "node":
        return "Nodes";
      case "action":
        return "Actions";
      case "setting":
        return "Settings";
      default:
        return type;
    }
  };

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
          {Object.keys(groupedItems).length === 0 ? (
            <div className="p-4 text-center text-muted-foreground">
              No results found
            </div>
          ) : (
            Object.entries(groupedItems).map(([type, items]) => (
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
