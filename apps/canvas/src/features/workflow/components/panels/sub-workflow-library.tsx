import React, { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { cn } from "@/lib/utils";

interface SubWorkflowSummary {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  nodeCount: number;
  edgeCount: number;
}

interface SubWorkflowLibraryProps {
  subWorkflows: SubWorkflowSummary[];
  onInsert?: (workflowId: string) => void;
  className?: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  all: "All",
  automation: "Automation",
  ai: "AI",
  data: "Data",
  communication: "Communication",
};

export default function SubWorkflowLibrary({
  subWorkflows,
  onInsert,
  className,
}: SubWorkflowLibraryProps) {
  const [activeCategory, setActiveCategory] = useState<string>("all");

  const categories = useMemo(() => {
    const unique = new Set<string>(["all"]);
    for (const workflow of subWorkflows) {
      unique.add(workflow.category);
    }
    return Array.from(unique);
  }, [subWorkflows]);

  const filtered = useMemo(() => {
    if (activeCategory === "all") {
      return subWorkflows;
    }
    return subWorkflows.filter(
      (workflow) => workflow.category === activeCategory,
    );
  }, [activeCategory, subWorkflows]);

  if (subWorkflows.length === 0) {
    return (
      <div
        className={cn(
          "rounded-lg border border-dashed border-border bg-muted/20 p-6 text-sm text-muted-foreground",
          className,
        )}
      >
        No reusable sub-workflows are available yet. Create a workflow and save
        it to reuse it here.
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      <Tabs value={activeCategory} onValueChange={setActiveCategory}>
        <TabsList className="w-full justify-start overflow-x-auto">
          {categories.map((category) => (
            <TabsTrigger key={category} value={category} className="capitalize">
              {CATEGORY_LABELS[category] ?? category}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={activeCategory} className="m-0">
          <ScrollArea className="max-h-[420px] pr-2">
            <div className="grid gap-4 md:grid-cols-2">
              {filtered.map((workflow) => (
                <Card key={workflow.id} className="border-border/70">
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between text-base">
                      <span>{workflow.name}</span>
                      <Badge variant="secondary" className="capitalize">
                        {CATEGORY_LABELS[workflow.category] ??
                          workflow.category}
                      </Badge>
                    </CardTitle>
                    <CardDescription>{workflow.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{workflow.nodeCount} nodes</span>
                      <span aria-hidden="true">•</span>
                      <span>{workflow.edgeCount} connections</span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {workflow.tags.map((tag) => (
                        <Badge
                          key={`${workflow.id}-${tag}`}
                          variant="outline"
                          className="text-xs capitalize"
                        >
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button
                      variant="secondary"
                      className="w-full"
                      onClick={() => onInsert?.(workflow.id)}
                    >
                      Insert into canvas
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
