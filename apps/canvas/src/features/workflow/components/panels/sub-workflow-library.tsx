import React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";

interface SubWorkflowTemplateSummary {
  id: string;
  name: string;
  description?: string;
  tags: string[];
  nodeCount: number;
  edgeCount: number;
  updatedAt: string;
}

interface SubWorkflowLibraryProps {
  subWorkflows: SubWorkflowTemplateSummary[];
  onInsert?: (templateId: string) => void;
  className?: string;
}

export default function SubWorkflowLibrary({
  subWorkflows,
  onInsert,
  className,
}: SubWorkflowLibraryProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Sub-Workflow Library</CardTitle>
        <CardDescription>
          Discover reusable workflow fragments and drop them directly onto the
          canvas.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {subWorkflows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No reusable flows are available yet. Save a workflow as a template
            to surface it here.
          </p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {subWorkflows.map((template) => (
              <div
                key={template.id}
                className="border border-border rounded-xl p-4 flex flex-col gap-3 bg-card"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-base">{template.name}</h3>
                    <p className="text-sm text-muted-foreground">
                      {template.description ?? "Reusable workflow fragment."}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {new Date(template.updatedAt).toLocaleDateString()}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{template.nodeCount} nodes</Badge>
                  <Badge variant="secondary">{template.edgeCount} edges</Badge>
                  {template.tags.slice(0, 3).map((tag) => (
                    <Badge key={tag} variant="outline" className="capitalize">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <Button
                  onClick={() => onInsert?.(template.id)}
                  variant="secondary"
                  className="self-start"
                >
                  Insert onto canvas
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
