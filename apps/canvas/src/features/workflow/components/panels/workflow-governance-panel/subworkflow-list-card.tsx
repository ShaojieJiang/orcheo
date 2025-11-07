import { Plus, Puzzle, Trash2, CalendarClock } from "lucide-react";

import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";

import type { SubworkflowTemplate } from "./types";

interface SubworkflowListCardProps {
  subworkflows: SubworkflowTemplate[];
  onCreateSubworkflow: () => void;
  onInsertSubworkflow: (subworkflow: SubworkflowTemplate) => void;
  onDeleteSubworkflow: (id: string) => void;
}

const STATUS_LABEL: Record<SubworkflowTemplate["status"], string> = {
  stable: "Stable",
  beta: "Beta",
  deprecated: "Deprecated",
};

function renderSubworkflowStatus(status: SubworkflowTemplate["status"]) {
  if (status === "stable") {
    return <Badge variant="secondary">{STATUS_LABEL[status]}</Badge>;
  }

  if (status === "deprecated") {
    return (
      <Badge
        variant="destructive"
        className="bg-destructive/10 text-destructive"
      >
        {STATUS_LABEL[status]}
      </Badge>
    );
  }

  return <Badge variant="outline">{STATUS_LABEL[status]}</Badge>;
}

export function SubworkflowListCard({
  subworkflows,
  onCreateSubworkflow,
  onInsertSubworkflow,
  onDeleteSubworkflow,
}: SubworkflowListCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <CardTitle>Reusable Sub-workflows</CardTitle>
          <CardDescription>
            Curate reusable workflow templates to accelerate delivery across
            teams.
          </CardDescription>
        </div>
        <Button onClick={onCreateSubworkflow} className="mt-2 md:mt-0">
          <Plus className="mr-2 h-4 w-4" />
          New sub-workflow
        </Button>
      </CardHeader>
      <CardContent>
        {subworkflows.length === 0 ? (
          <div className="rounded-lg border border-dashed border-muted-foreground/50 p-10 text-center text-sm text-muted-foreground">
            No reusable sub-workflows yet. Create your first template to share
            best practices with your team.
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {subworkflows.map((subworkflow) => (
              <div
                key={subworkflow.id}
                className="flex h-full flex-col justify-between rounded-lg border border-border bg-muted/30 p-5"
              >
                <div className="space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold leading-tight">
                        {subworkflow.name}
                      </h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {subworkflow.description}
                      </p>
                    </div>
                    {renderSubworkflowStatus(subworkflow.status)}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {subworkflow.tags.map((tag) => (
                      <Badge key={`${subworkflow.id}-${tag}`} variant="outline">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="mt-6 space-y-3 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Puzzle className="h-4 w-4" />
                    {subworkflow.usageCount}{" "}
                    {subworkflow.usageCount === 1 ? "workflow" : "workflows"}{" "}
                    rely on this template
                  </div>
                  <div className="flex items-center gap-2">
                    <CalendarClock className="h-4 w-4" />
                    Updated {new Date(subworkflow.lastUpdated).toLocaleString()}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="uppercase">
                      v{subworkflow.version}
                    </Badge>
                    Versioned for consistency
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap justify-end gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onInsertSubworkflow(subworkflow)}
                  >
                    Insert into canvas
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    onClick={() => onDeleteSubworkflow(subworkflow.id)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
