import { useRef, useState } from "react";
import type { KeyboardEvent, MouseEvent, SyntheticEvent } from "react";
import { toast } from "@/hooks/use-toast";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Copy,
  Download,
  FolderPlus,
  MoreHorizontal,
  Pencil,
  Star,
  Trash,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { type Workflow } from "@features/workflow/data/workflow-data";
import { WorkflowThumbnail } from "./workflow-thumbnail";

interface WorkflowCardProps {
  workflow: Workflow;
  isTemplate: boolean;
  onOpenWorkflow: (workflowId: string) => void;
  onUseTemplate: (workflowId: string) => void;
  onDuplicateWorkflow: (workflowId: string) => void;
  onExportWorkflow: (workflow: Workflow) => void;
  onDeleteWorkflow: (workflowId: string, workflowName: string) => void;
}

export const WorkflowCard = ({
  workflow,
  isTemplate,
  onOpenWorkflow,
  onUseTemplate,
  onDuplicateWorkflow,
  onExportWorkflow,
  onDeleteWorkflow,
}: WorkflowCardProps) => {
  const updatedLabel = new Date(
    workflow.updatedAt || workflow.createdAt,
  ).toLocaleDateString();
  const isClickable = !isTemplate;
  const suppressCardOpenRef = useRef(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const suppressCardOpen = () => {
    suppressCardOpenRef.current = true;
    setTimeout(() => {
      suppressCardOpenRef.current = false;
    }, 0);
  };

  const handleCardOpen = (event: MouseEvent<HTMLDivElement>) => {
    if (isClickable) {
      if (isMenuOpen) {
        return;
      }
      if (suppressCardOpenRef.current) {
        return;
      }
      const target = event.target as HTMLElement;
      if (target.closest('[data-card-action="true"]')) {
        return;
      }
      onOpenWorkflow(workflow.id);
    }
  };

  const handleCardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!isClickable) {
      return;
    }
    const target = event.target as HTMLElement;
    if (target.closest('[data-card-action="true"]')) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenWorkflow(workflow.id);
    }
  };

  const stopPropagation = (event: SyntheticEvent) => {
    event.stopPropagation();
    suppressCardOpen();
  };

  return (
    <Card
      className={cn(
        "overflow-hidden",
        isClickable && "cursor-pointer transition-colors hover:bg-muted/20",
      )}
      data-testid="workflow-card"
      onClick={handleCardOpen}
      onKeyDown={handleCardKeyDown}
      role={isClickable ? "button" : undefined}
      tabIndex={isClickable ? 0 : undefined}
    >
      <CardHeader className="px-3 pb-2 pt-3">
        <div className="flex items-start justify-between">
          <CardTitle className="text-base">{workflow.name}</CardTitle>
          <DropdownMenu
            open={isMenuOpen}
            onOpenChange={(open) => {
              setIsMenuOpen(open);
              if (!open) {
                suppressCardOpen();
              }
            }}
          >
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={stopPropagation}
                onPointerDown={stopPropagation}
                aria-label="Workflow actions"
                data-card-action="true"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {isTemplate ? (
                <>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      onUseTemplate(workflow.id);
                    }}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Use template
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      onExportWorkflow(workflow);
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export JSON
                  </DropdownMenuItem>
                </>
              ) : (
                <>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      onOpenWorkflow(workflow.id);
                    }}
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      onDuplicateWorkflow(workflow.id);
                    }}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Duplicate
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      onExportWorkflow(workflow);
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export JSON
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-red-600"
                    onSelect={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      onDeleteWorkflow(workflow.id, workflow.name);
                    }}
                  >
                    <Trash className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <CardDescription className="line-clamp-1">
          {workflow.description || "No description provided"}
        </CardDescription>

        {isTemplate && workflow.sourceExample && (
          <p className="mt-1 line-clamp-1 text-xs text-muted-foreground/80">
            Based on {workflow.sourceExample}
          </p>
        )}
      </CardHeader>

      <CardContent className="px-3 pb-2">
        <WorkflowThumbnail workflow={workflow} />
        <div className="mt-2 flex flex-wrap gap-1">
          {workflow.tags.slice(0, 2).map((tag) => (
            <Badge key={tag} variant="secondary" className="text-xs">
              {tag}
            </Badge>
          ))}
          {workflow.tags.length > 2 && (
            <Badge variant="secondary" className="text-xs">
              +{workflow.tags.length - 2} more
            </Badge>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex justify-between px-3 pb-3 pt-2 text-xs text-muted-foreground">
        <div className="flex items-center">
          <Avatar className="mr-1 h-5 w-5">
            <AvatarImage src={workflow.owner.avatar} />
            <AvatarFallback>{workflow.owner.name.charAt(0)}</AvatarFallback>
          </Avatar>
          <div className="flex items-center gap-1">
            <span>{updatedLabel}</span>
            {workflow.lastRun?.status === "success" && (
              <CheckCircle className="h-3 w-3 text-green-500" />
            )}
            {workflow.lastRun?.status === "error" && (
              <AlertCircle className="h-3 w-3 text-red-500" />
            )}
            {workflow.lastRun?.status === "running" && (
              <Clock className="h-3 w-3 animate-pulse text-blue-500" />
            )}
          </div>
        </div>

        <div className="flex gap-1">
          {isTemplate ? (
            <Button
              size="sm"
              className="h-7 px-3 text-xs"
              data-card-action="true"
              onClick={(event) => {
                stopPropagation(event);
                onUseTemplate(workflow.id);
              }}
              onPointerDown={stopPropagation}
            >
              <FolderPlus className="mr-1 h-3 w-3" />
              Use template
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label="Favorite workflow"
                data-card-action="true"
                onClick={(event) => {
                  stopPropagation(event);
                  toast({
                    title: "Favorites coming soon",
                    description: `We'll remember ${workflow.name} as a favorite soon.`,
                  });
                }}
                onPointerDown={stopPropagation}
              >
                <Star className="h-3 w-3" />
              </Button>
              <Button
                size="sm"
                className="h-7 px-2 text-xs"
                data-card-action="true"
                onClick={(event) => {
                  stopPropagation(event);
                  onOpenWorkflow(workflow.id);
                }}
                onPointerDown={stopPropagation}
              >
                <Pencil className="mr-1 h-3 w-3" />
                Edit
              </Button>
            </>
          )}
        </div>
      </CardFooter>
    </Card>
  );
};
