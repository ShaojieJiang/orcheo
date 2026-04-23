import { Button } from "@/design-system/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Loader2, Zap } from "lucide-react";
import { type Workflow } from "@features/workflow/data/workflow-data";
import { WorkflowCard } from "./workflow-card";
import {
  type WorkflowGalleryTab,
  type WorkflowGalleryTabCounts,
} from "./types";

interface WorkflowGalleryTabsProps {
  selectedTab: WorkflowGalleryTab;
  onSelectedTabChange: (value: WorkflowGalleryTab) => void;
  isLoading: boolean;
  sortedWorkflows: Workflow[];
  tabCounts: WorkflowGalleryTabCounts;
  isTemplateView: boolean;
  searchQuery: string;
  onImportStarterPack: () => void;
  onOpenWorkflow: (workflowId: string) => void;
  onUseTemplate: (workflowId: string) => void;
  onExportWorkflow: (workflow: Workflow) => void;
  onDeleteWorkflow: (
    workflowId: string,
    workflowName: string,
  ) => Promise<void> | void;
}

export const WorkflowGalleryTabs = ({
  selectedTab,
  onSelectedTabChange,
  isLoading,
  sortedWorkflows,
  tabCounts,
  isTemplateView,
  searchQuery,
  onImportStarterPack,
  onOpenWorkflow,
  onUseTemplate,
  onExportWorkflow,
  onDeleteWorkflow,
}: WorkflowGalleryTabsProps) => {
  return (
    <Tabs
      value={selectedTab}
      onValueChange={(value) =>
        onSelectedTabChange(value as WorkflowGalleryTab)
      }
      className="px-4"
    >
      <div className="mb-6 flex items-center justify-between">
        <TabsList>
          <TabsTrigger value="all" className="gap-2">
            <span>All</span>
            <span className="text-xs text-muted-foreground">
              {tabCounts.all}
            </span>
          </TabsTrigger>
          <TabsTrigger value="favorites" className="gap-2">
            <span>Favorites</span>
            <span className="text-xs text-muted-foreground">
              {tabCounts.favorites}
            </span>
          </TabsTrigger>
          <TabsTrigger value="shared" className="gap-2">
            <span>Shared with me</span>
            <span className="text-xs text-muted-foreground">
              {tabCounts.shared}
            </span>
          </TabsTrigger>
          <TabsTrigger value="templates" className="gap-2">
            <span>Templates</span>
            <span className="text-xs text-muted-foreground">
              {tabCounts.templates}
            </span>
          </TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value={selectedTab} className="mt-0">
        {isLoading && !isTemplateView ? (
          <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 text-center">
            <div className="rounded-full bg-muted p-4">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-medium">Loading workflows</h3>
              <p className="text-sm text-muted-foreground">
                Pulling your workspace from storage.
              </p>
            </div>
          </div>
        ) : sortedWorkflows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 rounded-full bg-muted p-4">
              <Zap className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="mb-2 text-lg font-medium">No workflows found</h3>
            <p className="mb-6 max-w-md text-muted-foreground">
              {searchQuery
                ? `No workflows match your search for "${searchQuery}"`
                : "Import starter workflows or use templates to get started."}
            </p>
            <div className="flex flex-col items-center gap-3">
              {!isTemplateView ? (
                <Button variant="outline" onClick={onImportStarterPack}>
                  Import Starter Pack
                </Button>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 pb-6 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
            {sortedWorkflows.map((workflow) => (
              <WorkflowCard
                key={workflow.id}
                workflow={workflow}
                isTemplate={isTemplateView}
                onOpenWorkflow={onOpenWorkflow}
                onUseTemplate={onUseTemplate}
                onExportWorkflow={onExportWorkflow}
                onDeleteWorkflow={onDeleteWorkflow}
              />
            ))}
          </div>
        )}
      </TabsContent>
    </Tabs>
  );
};
