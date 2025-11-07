import { useEffect, useMemo, useState } from "react";
import { toast } from "@/hooks/use-toast";
import {
  SAMPLE_WORKFLOWS,
  type Workflow,
} from "@features/workflow/data/workflow-data";
import {
  listWorkflows,
  type StoredWorkflow,
  WORKFLOW_STORAGE_EVENT,
} from "@features/workflow/lib/workflow-storage";
import {
  type WorkflowGalleryFilters,
  type WorkflowGallerySort,
  type WorkflowGalleryTab,
} from "./types";

interface WorkflowGalleryStateSlice {
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  selectedTab: WorkflowGalleryTab;
  setSelectedTab: (value: WorkflowGalleryTab) => void;
  sortBy: WorkflowGallerySort;
  setSortBy: (value: WorkflowGallerySort) => void;
  newFolderName: string;
  setNewFolderName: (value: string) => void;
  newWorkflowName: string;
  setNewWorkflowName: (value: string) => void;
  showNewFolderDialog: boolean;
  setShowNewFolderDialog: (value: boolean) => void;
  showNewWorkflowDialog: boolean;
  setShowNewWorkflowDialog: (value: boolean) => void;
  showFilterPopover: boolean;
  setShowFilterPopover: (value: boolean) => void;
  filters: WorkflowGalleryFilters;
  setFilters: (value: WorkflowGalleryFilters) => void;
  sortedWorkflows: Workflow[];
  isTemplateView: boolean;
  templates: Workflow[];
}

const DEFAULT_FILTERS: WorkflowGalleryFilters = {
  owner: {
    me: true,
    shared: true,
  },
  status: {
    active: true,
    draft: true,
    archived: false,
  },
  tags: {
    favorite: false,
    template: false,
    production: false,
    development: false,
  },
};

export const useWorkflowGalleryState = (): WorkflowGalleryStateSlice => {
  const [workflows, setWorkflows] = useState<StoredWorkflow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTab, setSelectedTab] = useState<WorkflowGalleryTab>("all");
  const [sortBy, setSortBy] = useState<WorkflowGallerySort>("updated");
  const [newFolderName, setNewFolderName] = useState("");
  const [newWorkflowName, setNewWorkflowName] = useState("");
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false);
  const [showNewWorkflowDialog, setShowNewWorkflowDialog] = useState(false);
  const [showFilterPopover, setShowFilterPopover] = useState(false);
  const [filters, setFilters] =
    useState<WorkflowGalleryFilters>(DEFAULT_FILTERS);

  useEffect(() => {
    let isMounted = true;

    const load = async () => {
      try {
        const items = await listWorkflows();
        if (isMounted) {
          setWorkflows(items);
        }
      } catch (error) {
        if (!isMounted) {
          return;
        }

        console.error("Failed to load workflows", error);
        toast({
          title: "Unable to load workflows",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    };

    void load();

    const targetWindow = typeof window !== "undefined" ? window : undefined;
    if (targetWindow) {
      const handler = () => {
        void load();
      };
      targetWindow.addEventListener(WORKFLOW_STORAGE_EVENT, handler);

      return () => {
        isMounted = false;
        targetWindow.removeEventListener(WORKFLOW_STORAGE_EVENT, handler);
      };
    }

    return () => {
      isMounted = false;
    };
  }, []);

  const templates = useMemo(() => SAMPLE_WORKFLOWS, []);
  const defaultOwnerId = templates[0]?.owner.id ?? "user-1";
  const isTemplateView = selectedTab === "templates";

  const filteredWorkflows = useMemo(() => {
    const collection: Workflow[] = isTemplateView ? templates : workflows;
    const query = searchQuery.toLowerCase();

    return collection.filter((workflow) => {
      const matchesSearch =
        workflow.name.toLowerCase().includes(query) ||
        (workflow.description &&
          workflow.description.toLowerCase().includes(query));

      if (!matchesSearch) {
        return false;
      }

      if (isTemplateView) {
        return workflow.tags.includes("template");
      }

      if (selectedTab === "favorites") {
        return workflow.tags.includes("favorite");
      }

      if (selectedTab === "shared") {
        return workflow.owner?.id !== defaultOwnerId;
      }

      if (selectedTab === "templates") {
        return workflow.tags.includes("template");
      }

      return true;
    });
  }, [
    defaultOwnerId,
    isTemplateView,
    searchQuery,
    selectedTab,
    templates,
    workflows,
  ]);

  const sortedWorkflows = useMemo(() => {
    return [...filteredWorkflows].sort((a, b) => {
      if (sortBy === "name") {
        return a.name.localeCompare(b.name);
      }
      if (sortBy === "updated") {
        return (
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
      }
      if (sortBy === "created") {
        return (
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      }
      return 0;
    });
  }, [filteredWorkflows, sortBy]);

  return {
    searchQuery,
    setSearchQuery,
    selectedTab,
    setSelectedTab,
    sortBy,
    setSortBy,
    newFolderName,
    setNewFolderName,
    newWorkflowName,
    setNewWorkflowName,
    showNewFolderDialog,
    setShowNewFolderDialog,
    showNewWorkflowDialog,
    setShowNewWorkflowDialog,
    showFilterPopover,
    setShowFilterPopover,
    filters,
    setFilters,
    sortedWorkflows,
    isTemplateView,
    templates,
  };
};
