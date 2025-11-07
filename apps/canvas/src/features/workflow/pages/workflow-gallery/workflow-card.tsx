import { Link } from "react-router-dom";
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

  return (
    <Card className="overflow-hidden">
      <CardHeader className="px-3 pb-2 pt-3">
        <div className="flex items-start justify-between">
          <CardTitle className="text-base">{workflow.name}</CardTitle>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-7 w-7">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {isTemplate ? (
                <>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
                      onUseTemplate(workflow.id);
                    }}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Use template
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
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
                      onOpenWorkflow(workflow.id);
                    }}
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
                      onDuplicateWorkflow(workflow.id);
                    }}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Duplicate
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={(event) => {
                      event.preventDefault();
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
              onClick={() => onUseTemplate(workflow.id)}
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
                onClick={() =>
                  toast({
                    title: "Favorites coming soon",
                    description: `We'll remember ${workflow.name} as a favorite soon.`,
                  })
                }
              >
                <Star className="h-3 w-3" />
              </Button>
              <Link to={`/workflow-canvas/${workflow.id}`}>
                <Button size="sm" className="h-7 px-2 text-xs">
                  <Pencil className="mr-1 h-3 w-3" />
                  Edit
                </Button>
              </Link>
            </>
          )}
        </div>
      </CardFooter>
    </Card>
  );
};
