import { Button } from "@/design-system/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import {
  Bug,
  Copy,
  Download,
  GitBranch,
  MoreHorizontal,
  Pause,
  Play,
  Save,
  Search,
  Share,
  Upload,
} from "lucide-react";

import type { WorkflowControlsProps } from "./types";

type ActionControlGroupProps = Pick<
  WorkflowControlsProps,
  | "isRunning"
  | "onPause"
  | "onRun"
  | "onSave"
  | "onDuplicate"
  | "onExport"
  | "onImport"
  | "onShare"
  | "onVersionHistory"
  | "onToggleSearch"
  | "isSearchOpen"
>;

export function ActionControlGroup({
  isRunning = false,
  onPause,
  onRun,
  onSave,
  onDuplicate,
  onExport,
  onImport,
  onShare,
  onVersionHistory,
  onToggleSearch,
  isSearchOpen = false,
}: ActionControlGroupProps) {
  return (
    <div className="flex items-center gap-1 border border-border rounded-md bg-background p-1">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={isRunning ? onPause : onRun}
              aria-label={isRunning ? "Pause workflow" : "Run workflow"}
            >
              {isRunning ? (
                <Pause className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>{isRunning ? "Pause Execution" : "Run Workflow"}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onSave}
              aria-label="Save workflow"
            >
              <Save className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Save Workflow</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              aria-label="Debug workflow"
            >
              <Bug className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Debug Mode</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={isSearchOpen ? "secondary" : "ghost"}
              size="icon"
              className="h-8 w-8"
              onClick={onToggleSearch}
              aria-label={isSearchOpen ? "Hide search" : "Search nodes"}
              aria-pressed={isSearchOpen}
            >
              <Search className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Search Nodes (Ctrl+F)</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DropdownMenu>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  aria-label="More actions"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent>
              <p>More Actions</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={(event) => {
              event.preventDefault();
              onDuplicate?.();
            }}
            disabled={!onDuplicate}
            data-testid="duplicate-workflow-menu-item"
          >
            <Copy className="mr-2 h-4 w-4" />
            <span>Duplicate</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={(event) => {
              event.preventDefault();
              onShare?.();
            }}
            disabled={!onShare}
          >
            <Share className="mr-2 h-4 w-4" />
            <span>Share</span>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={(event) => {
              event.preventDefault();
              onExport?.();
            }}
            disabled={!onExport}
          >
            <Download className="mr-2 h-4 w-4" />
            <span>Export</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={(event) => {
              event.preventDefault();
              onImport?.();
            }}
            disabled={!onImport}
          >
            <Upload className="mr-2 h-4 w-4" />
            <span>Import</span>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={(event) => {
              event.preventDefault();
              onVersionHistory?.();
            }}
            disabled={!onVersionHistory}
          >
            <GitBranch className="mr-2 h-4 w-4" />
            <span>Version History</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
