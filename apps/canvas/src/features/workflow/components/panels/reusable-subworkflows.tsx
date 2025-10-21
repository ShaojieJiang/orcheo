import React, { useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import { Separator } from "@/design-system/ui/separator";
import { Clock3, Link2, Plus } from "lucide-react";

import type { ReusableSubWorkflow } from "@features/workflow/data/workflow-data";

interface ReusableSubworkflowLibraryProps {
  subworkflows: ReusableSubWorkflow[];
  linkedSubworkflows: string[];
  onInsert: (subworkflowId: string) => void;
  onToggleLinked: (subworkflowId: string, linked: boolean) => void;
}

export default function ReusableSubworkflowLibrary({
  subworkflows,
  linkedSubworkflows,
  onInsert,
  onToggleLinked,
}: ReusableSubworkflowLibraryProps) {
  const linkedSet = useMemo(
    () => new Set(linkedSubworkflows),
    [linkedSubworkflows],
  );

  if (subworkflows.length === 0) {
    return (
      <Card className="border-dashed border-border/70 bg-muted/40">
        <CardHeader>
          <CardTitle className="text-base">
            No reusable sub-workflows yet
          </CardTitle>
          <CardDescription>
            Start by publishing a workflow segment to make it available as a
            reusable building block.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {subworkflows.map((subworkflow) => {
        const isLinked = linkedSet.has(subworkflow.id);

        return (
          <Card key={subworkflow.id} className="border-border/70">
            <CardHeader className="space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle className="text-lg">{subworkflow.name}</CardTitle>
                  <CardDescription className="mt-1">
                    {subworkflow.description}
                  </CardDescription>
                </div>
                {isLinked && (
                  <Badge variant="secondary" className="shrink-0">
                    Linked
                  </Badge>
                )}
              </div>

              <div className="flex flex-wrap gap-2 text-xs">
                <Badge variant="outline" className="capitalize">
                  {subworkflow.category}
                </Badge>
                {subworkflow.tags.map((tag) => (
                  <Badge key={`${subworkflow.id}-${tag}`} variant="outline">
                    #{tag}
                  </Badge>
                ))}
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <Clock3 className="h-3.5 w-3.5" />
                  {subworkflow.estimatedDurationMinutes}-minute run time
                </span>
                <span className="inline-flex items-center gap-1">
                  <Link2 className="h-3.5 w-3.5" />
                  Updated{" "}
                  {new Date(subworkflow.lastUpdated).toLocaleDateString()}
                </span>
              </div>

              <Separator />

              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm text-muted-foreground">
                  {isLinked
                    ? "This workflow will be included when the canvas is published."
                    : "Link this reusable flow to include it at publish time."}
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant={isLinked ? "secondary" : "outline"}
                    onClick={() => onToggleLinked(subworkflow.id, !isLinked)}
                  >
                    {isLinked ? "Remove link" : "Mark as linked"}
                  </Button>

                  <Button
                    size="sm"
                    onClick={() => onInsert(subworkflow.id)}
                    variant="default"
                  >
                    <Plus className="mr-1.5 h-4 w-4" />
                    Insert on canvas
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
