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
        <TabsList className="h-9">
          <TabsTrigger value="canvas" className="gap-1.5 text-sm px-3 py-1.5">
            Editor
          </TabsTrigger>
          <TabsTrigger
            value="execution"
            className="gap-1.5 text-sm px-3 py-1.5"
          >
            Execution
          </TabsTrigger>
          <TabsTrigger
            value="readiness"
            className="gap-1.5 text-sm px-3 py-1.5"
          >
            Readiness
            {readinessAlertCount > 0 && (
              <Badge variant="destructive" className="ml-1 text-xs px-1 py-0">
                {readinessAlertCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="settings" className="gap-1.5 text-sm px-3 py-1.5">
            Settings
          </TabsTrigger>
        </TabsList>
      </Tabs>
    </div>
  );
}
