import React from "react";
import { Button } from "@/design-system/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Play,
  Pause,
  Save,
  Copy,
  Download,
  Upload,
  RotateCcw,
  RotateCw,
  History,
  Bug,
  MoreHorizontal,
  Share,
  GitBranch,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface WorkflowControlsProps {
  isRunning?: boolean;
  onRun?: () => void;
  onPause?: () => void;
  onSave?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  onDuplicate?: () => void;
  onExport?: () => void;
  onImport?: () => void;
  onShare?: () => void;
  onVersionHistory?: () => void;
  onSearchToggle?: () => void;
  className?: string;
}

export default function WorkflowControls({
  isRunning = false,
  onRun,
  onPause,
  onSave,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
  onDuplicate,
  onExport,
  onImport,
  onShare,
  onVersionHistory,
  onSearchToggle,
  className,
}: WorkflowControlsProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
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
                onClick={onSearchToggle}
                aria-label="Search nodes"
                disabled={!onSearchToggle}
              >
                <Search className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Search &amp; Filter (Ctrl+F)</p>
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

      <div className="flex items-center gap-1 border border-border rounded-md bg-background p-1">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={onUndo}
                disabled={!canUndo}
                aria-label="Undo"
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Undo (Ctrl+Z)</p>
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
                onClick={onRedo}
                disabled={!canRedo}
                aria-label="Redo"
              >
                <RotateCw className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Redo (Ctrl+Y)</p>
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
                aria-label="History"
              >
                <History className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>History</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  );
}
