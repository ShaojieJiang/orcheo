import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Badge } from "@/design-system/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import {
  Search,
  Plus,
  FolderPlus,
  Clock,
  CheckCircle,
  AlertCircle,
  MoreHorizontal,
  Copy,
  Download,
  Trash,
  Pencil,
  Star,
  Filter,
  ArrowUpDown,
  Zap,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/design-system/ui/dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/design-system/ui/popover";
import { Checkbox } from "@/design-system/ui/checkbox";
import { Label } from "@/design-system/ui/label";

import TopNavigation from "@features/shared/components/top-navigation";
import {
  SAMPLE_WORKFLOWS,
  type Workflow,
} from "@features/workflow/data/workflow-data";
import {
  createWorkflow,
  createWorkflowFromTemplate,
  deleteWorkflow,
  duplicateWorkflow,
  listWorkflows,
  type StoredWorkflow,
  WORKFLOW_STORAGE_EVENT,
} from "@features/workflow/lib/workflow-storage";
import { toast } from "@/hooks/use-toast";

export default function WorkflowGallery() {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<StoredWorkflow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTab, setSelectedTab] = useState("all");
  const [sortBy, setSortBy] = useState("updated");
  const [newFolderName, setNewFolderName] = useState("");
  const [newWorkflowName, setNewWorkflowName] = useState("");
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false);
  const [showNewWorkflowDialog, setShowNewWorkflowDialog] = useState(false);
  const [showFilterPopover, setShowFilterPopover] = useState(false);
  const [filters, setFilters] = useState({
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
  });

  useEffect(() => {
    let isMounted = true;

    const load = async () => {
      try {
        const items = await listWorkflows();
        if (isMounted) {
          setWorkflows(items);
        }
      } catch (error) {
        if (isMounted) {
          console.error("Failed to load workflows", error);
          toast({
            title: "Unable to load workflows",
            description:
              error instanceof Error ? error.message : "Unknown error occurred",
            variant: "destructive",
          });
        }
      }
    };

    void load();

    if (typeof window !== "undefined") {
      const handler = () => {
        void load();
      };
      window.addEventListener(WORKFLOW_STORAGE_EVENT, handler);
      return () => {
        isMounted = false;
        window.removeEventListener(WORKFLOW_STORAGE_EVENT, handler);
      };
    }

    return () => {
      isMounted = false;
    };
  }, []);

  const templates = useMemo(() => SAMPLE_WORKFLOWS, []);
  const defaultOwnerId = templates[0]?.owner.id ?? "user-1";
  const isTemplateView = selectedTab === "templates";

  // Filter workflows based on search query and selected tab
  const filteredWorkflows = useMemo(() => {
    const collection = isTemplateView ? templates : workflows;

    return collection.filter((workflow) => {
      const matchesSearch =
        workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (workflow.description &&
          workflow.description
            .toLowerCase()
            .includes(searchQuery.toLowerCase()));

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

  // Sort workflows
  const sortedWorkflows = useMemo(() => {
    return [...filteredWorkflows].sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "updated")
        return (
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
      if (sortBy === "created")
        return (
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      return 0;
    });
  }, [filteredWorkflows, sortBy]);

  const handleCreateFolder = () => {
    toast({
      title: "Folder creation coming soon",
      description: newFolderName
        ? `We'll create "${newFolderName}" once persistence is wired up.`
        : "Folder creation will be available in a future update.",
    });
    setNewFolderName("");
    setShowNewFolderDialog(false);
  };

  const handleCreateWorkflow = useCallback(async () => {
    const name = newWorkflowName.trim() || "Untitled Workflow";
    try {
      const workflow = await createWorkflow({
        name,
        description: "",
        tags: ["draft"],
        nodes: [],
        edges: [],
      });

      setNewWorkflowName("");
      setShowNewWorkflowDialog(false);
      setSelectedTab("all");

      toast({
        title: "Workflow created",
        description: `"${workflow.name}" is ready to edit.`,
      });

      navigate(`/workflow-canvas/${workflow.id}`);
    } catch (error) {
      toast({
        title: "Failed to create workflow",
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
      });
    }
  }, [navigate, newWorkflowName]);

  const handleUseTemplate = useCallback(
    async (templateId: string) => {
      try {
        const workflow = await createWorkflowFromTemplate(templateId);
        if (!workflow) {
          toast({
            title: "Template unavailable",
            description: "We couldn't find that template. Please try another.",
            variant: "destructive",
          });
          return;
        }

        setSelectedTab("all");

        toast({
          title: "Template copied",
          description: `"${workflow.name}" has been added to your workspace.`,
        });

        navigate(`/workflow-canvas/${workflow.id}`);
      } catch (error) {
        toast({
          title: "Failed to create workflow from template",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    },
    [navigate],
  );

  const handleDuplicateWorkflow = useCallback(
    async (workflowId: string) => {
      try {
        const copy = await duplicateWorkflow(workflowId);
        if (!copy) {
          toast({
            title: "Duplicate failed",
            description:
              "We couldn't duplicate this workflow. Please try again.",
            variant: "destructive",
          });
          return;
        }

        setSelectedTab("all");

        toast({
          title: "Workflow duplicated",
          description: `"${copy.name}" is ready to edit.`,
        });

        navigate(`/workflow-canvas/${copy.id}`);
      } catch (error) {
        toast({
          title: "Failed to duplicate workflow",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    },
    [navigate],
  );

  const handleExportWorkflow = (workflow: Workflow) => {
    try {
      const payload = {
        name: workflow.name,
        description: workflow.description,
        nodes: workflow.nodes,
        edges: workflow.edges,
      };
      const serialized = JSON.stringify(payload, null, 2);
      const blob = new Blob([serialized], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${
        workflow.name.replace(/\s+/g, "-").toLowerCase() || "workflow"
      }.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast({
        title: "Workflow exported",
        description: `Downloaded ${workflow.name}.json`,
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description:
          error instanceof Error ? error.message : "Unable to export workflow.",
        variant: "destructive",
      });
    }
  };

  const handleDeleteWorkflow = useCallback(
    async (workflowId: string, workflowName: string) => {
      try {
        await deleteWorkflow(workflowId);
        toast({
          title: "Workflow deleted",
          description: `"${workflowName}" has been removed from your workspace.`,
        });
      } catch (error) {
        toast({
          title: "Failed to delete workflow",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      }
    },
    [],
  );

  const handleApplyFilters = () => {
    toast({
      title: "Filters applied",
      description:
        "Filter changes will affect the gallery once data wiring is complete.",
    });
    setShowFilterPopover(false);
    // In a real app, this would update the filtered workflows
  };

  // Generate a simple thumbnail preview for a workflow
  const WorkflowThumbnail = ({ workflow }) => {
    const nodeColors = {
      trigger: "#f59e0b",
      api: "#3b82f6",
      function: "#8b5cf6",
      data: "#10b981",
      ai: "#6366f1",
      python: "#f97316",
    };

    return (
      <div className="w-full h-24 bg-muted/30 rounded-md overflow-hidden relative">
        <svg
          width="100%"
          height="100%"
          viewBox="0 0 200 100"
          className="absolute inset-0"
        >
          {/* Draw simplified nodes and connections */}
          {workflow.nodes.slice(0, 5).map((node, index) => {
            const x = 30 + (index % 3) * 70;
            const y = 30 + Math.floor(index / 3) * 40;
            const color = nodeColors[node.type] || "#99a1b3";

            return (
              <g key={node.id}>
                <rect
                  x={x - 15}
                  y={y - 10}
                  width={30}
                  height={20}
                  rx={4}
                  fill={color}
                  fillOpacity={0.3}
                  stroke={color}
                  strokeWidth={1}
                />
              </g>
            );
          })}

          {/* Draw simplified edges */}
          {workflow.edges.slice(0, 4).map((edge) => {
            const sourceIndex = workflow.nodes.findIndex(
              (n) => n.id === edge.source,
            );
            const targetIndex = workflow.nodes.findIndex(
              (n) => n.id === edge.target,
            );

            if (
              sourceIndex >= 0 &&
              targetIndex >= 0 &&
              sourceIndex < 5 &&
              targetIndex < 5
            ) {
              const sourceX = 30 + (sourceIndex % 3) * 70 + 15;
              const sourceY = 30 + Math.floor(sourceIndex / 3) * 40;
              const targetX = 30 + (targetIndex % 3) * 70 - 15;
              const targetY = 30 + Math.floor(targetIndex / 3) * 40;

              return (
                <path
                  key={edge.id}
                  d={`M${sourceX},${sourceY} C${sourceX + 20},${sourceY} ${targetX - 20},${targetY} ${targetX},${targetY}`}
                  stroke="#99a1b3"
                  strokeWidth={1}
                  fill="none"
                />
              );
            }
            return null;
          })}
        </svg>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-screen">
      <TopNavigation />

      <main className="flex-1 overflow-auto">
        <div className="h-full">
          <div className="flex flex-col h-[calc(100%-80px)]">
            {/* Main content */}
            <div className="flex-1 overflow-auto">
              <div className="flex flex-col md:flex-row gap-4 mb-6 items-start md:items-center p-4">
                <div className="flex items-center gap-2 md:order-2">
                  <Dialog
                    open={showNewFolderDialog}
                    onOpenChange={setShowNewFolderDialog}
                  >
                    <DialogTrigger asChild>
                      <Button variant="outline">
                        <FolderPlus className="mr-2 h-4 w-4" />
                        New Folder
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New Folder</DialogTitle>
                        <DialogDescription>
                          Enter a name for your new folder.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="py-4">
                        <Label htmlFor="folder-name">Folder Name</Label>
                        <Input
                          id="folder-name"
                          value={newFolderName}
                          onChange={(e) => setNewFolderName(e.target.value)}
                          placeholder="My Workflows"
                          className="mt-2"
                        />
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setShowNewFolderDialog(false)}
                        >
                          Cancel
                        </Button>
                        <Button onClick={handleCreateFolder}>
                          Create Folder
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>

                  <Dialog
                    open={showNewWorkflowDialog}
                    onOpenChange={setShowNewWorkflowDialog}
                  >
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="mr-2 h-4 w-4" />
                        Create Workflow
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New Workflow</DialogTitle>
                        <DialogDescription>
                          Enter a name for your new workflow.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="py-4">
                        <Label htmlFor="workflow-name">Workflow Name</Label>
                        <Input
                          id="workflow-name"
                          value={newWorkflowName}
                          onChange={(e) => setNewWorkflowName(e.target.value)}
                          placeholder="My New Workflow"
                          className="mt-2"
                        />
                      </div>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setShowNewWorkflowDialog(false)}
                        >
                          Cancel
                        </Button>
                        <Button onClick={handleCreateWorkflow}>
                          Create & Open
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>

                <div className="relative flex-1 md:order-1">
                  <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />

                  <Input
                    placeholder="Search workflows..."
                    className="pl-10"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                <div className="flex items-center gap-2 md:order-3">
                  <Select value={sortBy} onValueChange={setSortBy}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="Sort by" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="updated">
                        <div className="flex items-center">
                          <ArrowUpDown className="mr-2 h-4 w-4" />
                          Last Updated
                        </div>
                      </SelectItem>
                      <SelectItem value="created">
                        <div className="flex items-center">
                          <Clock className="mr-2 h-4 w-4" />
                          Creation Date
                        </div>
                      </SelectItem>
                      <SelectItem value="name">
                        <div className="flex items-center">
                          <ArrowUpDown className="mr-2 h-4 w-4" />
                          Name
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>

                  <Popover
                    open={showFilterPopover}
                    onOpenChange={setShowFilterPopover}
                  >
                    <PopoverTrigger asChild>
                      <Button variant="outline" size="icon">
                        <Filter className="h-4 w-4" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-80">
                      <div className="space-y-4">
                        <h4 className="font-medium">Filter Workflows</h4>

                        <div className="space-y-2">
                          <h5 className="text-sm font-medium">Owner</h5>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="owner-me"
                                checked={filters.owner.me}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    owner: { ...filters.owner, me: !!checked },
                                  })
                                }
                              />

                              <Label htmlFor="owner-me">Created by me</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="owner-shared"
                                checked={filters.owner.shared}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    owner: {
                                      ...filters.owner,
                                      shared: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="owner-shared">
                                Shared with me
                              </Label>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <h5 className="text-sm font-medium">Status</h5>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="status-active"
                                checked={filters.status.active}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    status: {
                                      ...filters.status,
                                      active: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="status-active">Active</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="status-draft"
                                checked={filters.status.draft}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    status: {
                                      ...filters.status,
                                      draft: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="status-draft">Draft</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="status-archived"
                                checked={filters.status.archived}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    status: {
                                      ...filters.status,
                                      archived: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="status-archived">Archived</Label>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <h5 className="text-sm font-medium">Tags</h5>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="tag-favorite"
                                checked={filters.tags.favorite}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    tags: {
                                      ...filters.tags,
                                      favorite: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="tag-favorite">Favorite</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="tag-template"
                                checked={filters.tags.template}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    tags: {
                                      ...filters.tags,
                                      template: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="tag-template">Template</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="tag-production"
                                checked={filters.tags.production}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    tags: {
                                      ...filters.tags,
                                      production: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="tag-production">Production</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <Checkbox
                                id="tag-development"
                                checked={filters.tags.development}
                                onCheckedChange={(checked) =>
                                  setFilters({
                                    ...filters,
                                    tags: {
                                      ...filters.tags,
                                      development: !!checked,
                                    },
                                  })
                                }
                              />

                              <Label htmlFor="tag-development">
                                Development
                              </Label>
                            </div>
                          </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowFilterPopover(false)}
                          >
                            Cancel
                          </Button>
                          <Button size="sm" onClick={handleApplyFilters}>
                            Apply Filters
                          </Button>
                        </div>
                      </div>
                    </PopoverContent>
                  </Popover>
                </div>
              </div>

              <Tabs
                value={selectedTab}
                onValueChange={setSelectedTab}
                className="px-4"
              >
                <div className="flex justify-between items-center mb-6">
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
                      <div className="rounded-full bg-muted p-4 mb-4">
                        <Zap className="h-8 w-8 text-muted-foreground" />
                      </div>
                      <h3 className="text-lg font-medium mb-2">
                        No workflows found
                      </h3>
                      <p className="text-muted-foreground mb-6 max-w-md">
                        {searchQuery
                          ? `No workflows match your search for "${searchQuery}"`
                          : "Get started by creating your first workflow"}
                      </p>
                      <Button onClick={() => setShowNewWorkflowDialog(true)}>
                        <Plus className="mr-2 h-4 w-4" />
                        Create Workflow
                      </Button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3 pb-6">
                      {sortedWorkflows.map((workflow) => {
                        const isTemplateCard = isTemplateView;
                        const updatedLabel = new Date(
                          workflow.updatedAt || workflow.createdAt,
                        ).toLocaleDateString();

                        return (
                          <Card key={workflow.id} className="overflow-hidden">
                            <CardHeader className="pb-2 px-3 pt-3">
                              <div className="flex justify-between items-start">
                                <CardTitle className="text-base">
                                  {workflow.name}
                                </CardTitle>
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-7 w-7"
                                    >
                                      <MoreHorizontal className="h-4 w-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    {isTemplateCard ? (
                                      <>
                                        <DropdownMenuItem
                                          onSelect={(event) => {
                                            event.preventDefault();
                                            handleUseTemplate(workflow.id);
                                          }}
                                        >
                                          <Copy className="mr-2 h-4 w-4" />
                                          Use template
                                        </DropdownMenuItem>
                                        <DropdownMenuItem
                                          onSelect={(event) => {
                                            event.preventDefault();
                                            handleExportWorkflow(workflow);
                                          }}
                                        >
                                          <Download className="mr-2 h-4 w-4" />
                                          Export JSON
                                        </DropdownMenuItem>
                                      </>
                                    ) : (
                                      <>
                                        <DropdownMenuItem
                                          onSelect={(event) => {
                                            event.preventDefault();
                                            navigate(
                                              `/workflow-canvas/${workflow.id}`,
                                            );
                                          }}
                                        >
                                          <Pencil className="mr-2 h-4 w-4" />
                                          Edit
                                        </DropdownMenuItem>
                                        <DropdownMenuItem
                                          onSelect={(event) => {
                                            event.preventDefault();
                                            handleDuplicateWorkflow(
                                              workflow.id,
                                            );
                                          }}
                                        >
                                          <Copy className="mr-2 h-4 w-4" />
                                          Duplicate
                                        </DropdownMenuItem>
                                        <DropdownMenuItem
                                          onSelect={(event) => {
                                            event.preventDefault();
                                            handleExportWorkflow(workflow);
                                          }}
                                        >
                                          <Download className="mr-2 h-4 w-4" />
                                          Export JSON
                                        </DropdownMenuItem>
                                        <DropdownMenuSeparator />
                                        <DropdownMenuItem
                                          className="text-red-600"
                                          onSelect={(event) => {
                                            event.preventDefault();
                                            handleDeleteWorkflow(
                                              workflow.id,
                                              workflow.name,
                                            );
                                          }}
                                        >
                                          <Trash className="mr-2 h-4 w-4" />
                                          Delete
                                        </DropdownMenuItem>
                                      </>
                                    )}
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </div>
                              <CardDescription className="line-clamp-1">
                                {workflow.description ||
                                  "No description provided"}
                              </CardDescription>
                              {isTemplateCard && workflow.sourceExample && (
                                <p className="text-xs text-muted-foreground/80 mt-1 line-clamp-1">
                                  Based on {workflow.sourceExample}
                                </p>
                              )}
                            </CardHeader>

                            <CardContent className="pb-2 px-3">
                              <WorkflowThumbnail workflow={workflow} />

                              <div className="flex flex-wrap gap-1 mt-2">
                                {workflow.tags.slice(0, 2).map((tag) => (
                                  <Badge
                                    key={tag}
                                    variant="secondary"
                                    className="text-xs"
                                  >
                                    {tag}
                                  </Badge>
                                ))}
                                {workflow.tags.length > 2 && (
                                  <Badge
                                    variant="secondary"
                                    className="text-xs"
                                  >
                                    +{workflow.tags.length - 2} more
                                  </Badge>
                                )}
                              </div>
                            </CardContent>

                            <CardFooter className="flex justify-between pt-2 px-3 pb-3">
                              <div className="flex items-center text-xs text-muted-foreground">
                                <Avatar className="h-5 w-5 mr-1">
                                  <AvatarImage src={workflow.owner.avatar} />

                                  <AvatarFallback>
                                    {workflow.owner.name.charAt(0)}
                                  </AvatarFallback>
                                </Avatar>
                                <div className="flex items-center">
                                  <span className="mr-1">{updatedLabel}</span>
                                  {workflow.lastRun && (
                                    <>
                                      {workflow.lastRun.status ===
                                        "success" && (
                                        <CheckCircle className="h-3 w-3 text-green-500" />
                                      )}
                                      {workflow.lastRun.status === "error" && (
                                        <AlertCircle className="h-3 w-3 text-red-500" />
                                      )}
                                      {workflow.lastRun.status ===
                                        "running" && (
                                        <Clock className="h-3 w-3 text-blue-500 animate-pulse" />
                                      )}
                                    </>
                                  )}
                                </div>
                              </div>

                              <div className="flex gap-1">
                                {isTemplateCard ? (
                                  <Button
                                    size="sm"
                                    className="h-7 text-xs px-3"
                                    onClick={() =>
                                      handleUseTemplate(workflow.id)
                                    }
                                  >
                                    <FolderPlus className="mr-1 h-3 w-3" />
                                    Use template
                                  </Button>
                                ) : (
                                  <>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-7 w-7"
                                      onClick={() =>
                                        toast({
                                          title: "Favorites coming soon",
                                          description: `We'll remember ${workflow.name} as a favorite soon.`,
                                        })
                                      }
                                    >
                                      <Star className="h-3 w-3" />
                                    </Button>
                                    <Link
                                      to={`/workflow-canvas/${workflow.id}`}
                                    >
                                      <Button
                                        size="sm"
                                        className="h-7 text-xs px-2"
                                      >
                                        <Pencil className="mr-1 h-3 w-3" />
                                        Edit
                                      </Button>
                                    </Link>
                                  </>
                                )}
                              </div>
                            </CardFooter>
                          </Card>
                        );
                      })}
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
