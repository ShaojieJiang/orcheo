import { Button } from "@/design-system/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Plus, Zap } from "lucide-react";
import { type Workflow } from "@features/workflow/data/workflow-data";
import { WorkflowCard } from "./workflow-card";
import { type WorkflowGalleryTab } from "./types";

interface WorkflowGalleryTabsProps {
  selectedTab: WorkflowGalleryTab;
  onSelectedTabChange: (value: WorkflowGalleryTab) => void;
  sortedWorkflows: Workflow[];
  isTemplateView: boolean;
  searchQuery: string;
  onCreateWorkflowRequest: () => void;
  onOpenWorkflow: (workflowId: string) => void;
  onUseTemplate: (workflowId: string) => void;
  onDuplicateWorkflow: (workflowId: string) => void;
  onExportWorkflow: (workflow: Workflow) => void;
  onDeleteWorkflow: (workflowId: string, workflowName: string) => void;
}

export const WorkflowGalleryTabs = ({
  selectedTab,
  onSelectedTabChange,
  sortedWorkflows,
  isTemplateView,
  searchQuery,
  onCreateWorkflowRequest,
  onOpenWorkflow,
  onUseTemplate,
  onDuplicateWorkflow,
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
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="favorites">Favorites</TabsTrigger>
          <TabsTrigger value="shared">Shared with me</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value={selectedTab} className="mt-0">
        {sortedWorkflows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 rounded-full bg-muted p-4">
              <Zap className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="mb-2 text-lg font-medium">No workflows found</h3>
            <p className="mb-6 max-w-md text-muted-foreground">
              {searchQuery
                ? `No workflows match your search for "${searchQuery}"`
                : "Get started by creating your first workflow"}
            </p>
            <Button onClick={onCreateWorkflowRequest}>
              <Plus className="mr-2 h-4 w-4" />
              Create Workflow
            </Button>
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
                onDuplicateWorkflow={onDuplicateWorkflow}
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
