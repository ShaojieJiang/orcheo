import React from "react";
import { Tabs, TabsList, TabsTrigger } from "@/design-system/ui/tabs";
import { Badge } from "@/design-system/ui/badge";

interface WorkflowTabsProps {
  activeTab: string;
  onTabChange: (value: string) => void;
  executionCount?: number;
  resourceCount?: number;
}

export default function WorkflowTabs({
  activeTab,
  onTabChange,
  executionCount = 0,
  resourceCount = 0,
}: WorkflowTabsProps) {
  return (
    <div className="border-b border-border">
      <Tabs value={activeTab} onValueChange={onTabChange} className="w-full">
        <TabsList className="h-12">
          <TabsTrigger value="canvas" className="gap-2">
            Canvas
          </TabsTrigger>
          <TabsTrigger value="execution" className="gap-2">
            Execution
            {executionCount > 0 && (
              <Badge variant="secondary" className="ml-1">
                {executionCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="resources" className="gap-2">
            Resources
            {resourceCount > 0 && (
              <Badge variant="secondary" className="ml-1">
                {resourceCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="settings" className="gap-2">
            Settings
          </TabsTrigger>
        </TabsList>
      </Tabs>
    </div>
  );
}
