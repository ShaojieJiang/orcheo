import React from "react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
  ContextMenuTrigger,
} from "@/design-system/ui/context-menu";
import {
  Copy,
  Trash,
  Scissors,
  ClipboardPaste,
  Group,
  Ungroup,
  Layers,
  Edit,
  Plus,
  ArrowRight,
  ArrowDown,
  ExternalLink,
  Maximize,
  Minimize,
} from "lucide-react";

interface WorkflowContextMenuProps {
  children: React.ReactNode;
  onAddNode?: () => void;
  onCopy?: () => void;
  onPaste?: () => void;
  onCut?: () => void;
  onDelete?: () => void;
  onDuplicate?: () => void;
  onGroup?: () => void;
  onUngroup?: () => void;
  onCollapseExpand?: () => void;
  onOpenInNewTab?: () => void;
  isNodeSelected?: boolean;
  isGroupSelected?: boolean;
  isCollapsed?: boolean;
  canPaste?: boolean;
}

export default function WorkflowContextMenu({
  children,
  onAddNode,
  onCopy,
  onPaste,
  onCut,
  onDelete,
  onDuplicate,
  onGroup,
  onUngroup,
  onCollapseExpand,
  onOpenInNewTab,
  isNodeSelected = false,
  isGroupSelected = false,
  isCollapsed = false,
  canPaste = false,
}: WorkflowContextMenuProps) {
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent className="w-64">
        {isNodeSelected ? (
          <>
            <ContextMenuItem onClick={onCopy} disabled={!isNodeSelected}>
              <Copy className="mr-2 h-4 w-4" />

              <span>Copy</span>
              <ContextMenuShortcut>⌘C</ContextMenuShortcut>
            </ContextMenuItem>
            <ContextMenuItem onClick={onCut} disabled={!isNodeSelected}>
              <Scissors className="mr-2 h-4 w-4" />

              <span>Cut</span>
              <ContextMenuShortcut>⌘X</ContextMenuShortcut>
            </ContextMenuItem>
            <ContextMenuItem onClick={onDuplicate} disabled={!isNodeSelected}>
              <Copy className="mr-2 h-4 w-4" />

              <span>Duplicate</span>
              <ContextMenuShortcut>⌘D</ContextMenuShortcut>
            </ContextMenuItem>
            <ContextMenuSeparator />

            <ContextMenuItem onClick={onDelete} disabled={!isNodeSelected}>
              <Trash className="mr-2 h-4 w-4" />

              <span>Delete</span>
              <ContextMenuShortcut>Del</ContextMenuShortcut>
            </ContextMenuItem>
            <ContextMenuSeparator />

            {isGroupSelected ? (
              <>
                <ContextMenuItem onClick={onUngroup}>
                  <Ungroup className="mr-2 h-4 w-4" />

                  <span>Ungroup</span>
                  <ContextMenuShortcut>⌘U</ContextMenuShortcut>
                </ContextMenuItem>
                <ContextMenuItem onClick={onCollapseExpand}>
                  {isCollapsed ? (
                    <>
                      <Maximize className="mr-2 h-4 w-4" />

                      <span>Expand</span>
                    </>
                  ) : (
                    <>
                      <Minimize className="mr-2 h-4 w-4" />

                      <span>Collapse</span>
                    </>
                  )}
                </ContextMenuItem>
                <ContextMenuItem onClick={onOpenInNewTab}>
                  <ExternalLink className="mr-2 h-4 w-4" />

                  <span>Open in New Tab</span>
                </ContextMenuItem>
              </>
            ) : (
              <ContextMenuItem onClick={onGroup} disabled={!isNodeSelected}>
                <Group className="mr-2 h-4 w-4" />

                <span>Group Selection</span>
                <ContextMenuShortcut>⌘G</ContextMenuShortcut>
              </ContextMenuItem>
            )}
          </>
        ) : (
          <>
            <ContextMenuItem onClick={onAddNode}>
              <Plus className="mr-2 h-4 w-4" />

              <span>Add Node</span>
            </ContextMenuItem>
            <ContextMenuItem onClick={onPaste} disabled={!canPaste}>
              <ClipboardPaste className="mr-2 h-4 w-4" />

              <span>Paste</span>
              <ContextMenuShortcut>⌘V</ContextMenuShortcut>
            </ContextMenuItem>
            <ContextMenuSub>
              <ContextMenuSubTrigger>
                <Layers className="mr-2 h-4 w-4" />

                <span>Add Node Type</span>
              </ContextMenuSubTrigger>
              <ContextMenuSubContent className="w-48">
                <ContextMenuItem>
                  <ArrowRight className="mr-2 h-4 w-4" />

                  <span>Trigger</span>
                </ContextMenuItem>
                <ContextMenuItem>
                  <ArrowDown className="mr-2 h-4 w-4" />

                  <span>Function</span>
                </ContextMenuItem>
                <ContextMenuItem>
                  <Edit className="mr-2 h-4 w-4" />

                  <span>Transform</span>
                </ContextMenuItem>
              </ContextMenuSubContent>
            </ContextMenuSub>
          </>
        )}
      </ContextMenuContent>
    </ContextMenu>
  );
}
