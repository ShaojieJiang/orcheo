import React from "react";
import { Tabs, TabsList, TabsTrigger } from "@/design-system/ui/tabs";
import { Badge } from "@/design-system/ui/badge";

interface WorkflowTabsProps {
  activeTab: string;
  onTabChange: (value: string) => void;
  readinessAlertCount?: number;
}

export default function WorkflowTabs({
  activeTab,
  onTabChange,
  readinessAlertCount = 0,
}: WorkflowTabsProps) {
  return (
    <div className="border-b border-border">
      <Tabs value={activeTab} onValueChange={onTabChange} className="w-full">
        <TabsList className="h-12">
          <TabsTrigger value="canvas" className="gap-2">
            Editor
          </TabsTrigger>
          <TabsTrigger value="execution" className="gap-2">
            Execution
          </TabsTrigger>
          <TabsTrigger value="readiness" className="gap-2">
            Readiness
            {readinessAlertCount > 0 && (
              <Badge variant="destructive" className="ml-1">
                {readinessAlertCount}
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
