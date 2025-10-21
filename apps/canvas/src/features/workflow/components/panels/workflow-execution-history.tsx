import React, { useState, useRef, useEffect } from "react";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import {
  ReactFlow,
  Background,
  Controls,
  Edge,
  Node,
  MiniMap,
  ConnectionLineType,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Clock,
  MessageSquare,
  Filter,
  RefreshCw,
  Copy,
  Trash,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface WorkflowNode {
  id: string;
  type: string;
  name: string;
  position: { x: number; y: number };
  status?: "success" | "error" | "running" | "idle" | "warning";
  details?: {
    method?: string;
    url?: string;
    message?: string;
    items?: number;
  };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
}

export interface WorkflowExecution {
  id: string;
  runId: string;
  status: "success" | "failed" | "partial" | "running";
  startTime: string;
  endTime?: string;
  duration: number;
  issues: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  logs: {
    timestamp: string;
    level: "INFO" | "DEBUG" | "ERROR" | "WARNING";
    message: string;
  }[];
}

interface WorkflowExecutionHistoryProps {
  executions: WorkflowExecution[];
  onViewDetails?: (execution: WorkflowExecution) => void;
  onRefresh?: () => void;
  onCopyToEditor?: (execution: WorkflowExecution) => void;
  onDelete?: (execution: WorkflowExecution) => void;
  className?: string;
  showList?: boolean;
  defaultSelectedExecution?: WorkflowExecution;
}

export default function WorkflowExecutionHistory({
  executions = [],
  onViewDetails,
  onRefresh,
  onCopyToEditor,
  onDelete,
  className,
  showList = true,
  defaultSelectedExecution,
}: WorkflowExecutionHistoryProps) {
  const [selectedExecution, setSelectedExecution] =
    useState<WorkflowExecution | null>(
      defaultSelectedExecution ||
        (executions.length > 0 ? executions[0] : null),
    );
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const resizingRef = useRef(false);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);

  useEffect(() => {
    if (defaultSelectedExecution) {
      setSelectedExecution(defaultSelectedExecution);
      return;
    }
    if (executions.length === 0) {
      setSelectedExecution(null);
      return;
    }
    setSelectedExecution((current) => {
      if (
        current &&
        executions.some((execution) => execution.id === current.id)
      ) {
        return current;
      }
      return executions[0];
    });
  }, [defaultSelectedExecution, executions]);

  const handleSelectExecution = (execution: WorkflowExecution) => {
    setSelectedExecution(execution);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();

    if (date.toDateString() === now.toDateString()) {
      return `Today, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    } else if (
      date.toDateString() ===
      new Date(now.setDate(now.getDate() - 1)).toDateString()
    ) {
      return `Yesterday, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    } else {
      return (
        date.toLocaleDateString([], {
          month: "short",
          day: "numeric",
          year: "numeric",
        }) +
        `, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
      );
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    const seconds = ms / 1000;
    return `${seconds.toFixed(1)}s`;
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status.toLowerCase()) {
      case "success":
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
      case "failed":
        return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
      case "partial":
        return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400";
      case "running":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400";
    }
  };

  // Convert workflow nodes to ReactFlow nodes
  const getReactFlowNodes = (): Node[] => {
    if (!selectedExecution) return [];

    return selectedExecution.nodes.map((node) => ({
      id: node.id,
      type: "default",
      position: node.position,
      style: {
        background: "none",
        border: "none",
        padding: 0,
        borderRadius: 0,
        width: "auto",
        boxShadow: "none",
      },
      data: {
        label: node.name,
        status: node.status,
        type: node.type,
        details: node.details,
      },
    }));
  };

  // Convert workflow edges to ReactFlow edges
  const getReactFlowEdges = (): Edge[] => {
    if (!selectedExecution) return [];

    return selectedExecution.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: selectedExecution.status === "running",
      style: { stroke: "#99a1b3", strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 20,
        height: 20,
      },
    }));
  };

  // Handle sidebar resizing
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    resizingRef.current = true;
    startXRef.current = e.clientX;
    startWidthRef.current = sidebarWidth;
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!resizingRef.current) return;
    const delta = e.clientX - startXRef.current;
    const newWidth = Math.max(
      200,
      Math.min(500, startWidthRef.current + delta),
    );
    setSidebarWidth(newWidth);
  };

  const handleMouseUp = () => {
    resizingRef.current = false;
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
  };

  // Cleanup event listeners
  useEffect(() => {
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={cn("flex flex-col h-full w-full overflow-hidden", className)}
    >
      <div className="flex flex-col md:flex-row h-full">
        {/* Executions List */}
        {showList && (
          <div
            className="w-full md:w-auto border-r border-border flex-shrink-0 relative"
            style={{ width: sidebarWidth }}
          >
            <div className="p-2 border-b border-border">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-xl font-bold">Executions</h2>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={onRefresh}
                    title="Refresh"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon" title="Filter">
                    <Filter className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
            <ScrollArea className="h-[calc(100%-3rem)]">
              <div className="p-2 overflow-auto">
                {executions.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No executions found
                  </div>
                ) : (
                  executions.map((execution) => (
                    <div
                      key={execution.id}
                      className={cn(
                        "border rounded-lg p-4 mb-2 cursor-pointer transition-colors",
                        selectedExecution?.id === execution.id
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/50",
                      )}
                      onClick={() => handleSelectExecution(execution)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Badge
                            className={cn(
                              getStatusBadgeClass(execution.status),
                            )}
                          >
                            {execution.status.charAt(0).toUpperCase() +
                              execution.status.slice(1)}
                          </Badge>
                          <span className="font-medium">
                            Run #{execution.runId}
                          </span>
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {formatDate(execution.startTime)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-4">
                          <div className="flex items-center gap-1">
                            <Clock className="h-4 w-4 text-muted-foreground" />

                            <span>{formatDuration(execution.duration)}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <MessageSquare className="h-4 w-4 text-muted-foreground" />

                            <span>
                              {execution.issues}{" "}
                              {execution.issues === 1 ? "issue" : "issues"}
                            </span>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2"
                            onClick={(e) => {
                              e.stopPropagation();
                              onViewDetails?.(execution);
                            }}
                          >
                            View Details
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
            {/* Resize handle */}
            <div
              className="absolute top-0 right-0 w-1 h-full cursor-col-resize bg-border hover:bg-primary/50 transition-colors"
              onMouseDown={handleMouseDown}
            />
          </div>
        )}

        {/* Execution Details */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedExecution ? (
            <>
              <div className="p-2 border-b border-border flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold flex items-center gap-2">
                    <Badge
                      className={cn(
                        getStatusBadgeClass(selectedExecution.status),
                      )}
                    >
                      {selectedExecution.status.charAt(0).toUpperCase() +
                        selectedExecution.status.slice(1)}
                    </Badge>
                    Run #{selectedExecution.runId}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onCopyToEditor?.(selectedExecution)}
                    title="Copy to editor"
                  >
                    <Copy className="h-4 w-4 mr-2" />
                    Copy to editor
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => onDelete?.(selectedExecution)}
                    title="Delete execution"
                  >
                    <Trash className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="flex-1 flex flex-col overflow-hidden">
                <div
                  className={cn(
                    "relative border border-border rounded-lg overflow-auto bg-muted/20 flex-1",
                    isFullscreen
                      ? "fixed inset-0 z-50 p-4 bg-background"
                      : "h-[calc(100%-3rem)]",
                  )}
                >
                  {/* ReactFlow Canvas */}
                  <div className="w-full h-full relative">
                    <ReactFlow
                      nodes={getReactFlowNodes()}
                      edges={getReactFlowEdges()}
                      fitView
                      fitViewOptions={{ padding: 0.2 }}
                      nodesDraggable={false}
                      nodesConnectable={false}
                      elementsSelectable={false}
                      zoomOnScroll={false}
                      zoomOnPinch={true}
                      panOnScroll={true}
                      connectionLineType={ConnectionLineType.SmoothStep}
                    >
                      <Background gap={15} size={1} color="#f0f0f0" />

                      <Controls
                        showInteractive={false}
                        position="bottom-right"
                      />

                      <MiniMap
                        nodeStrokeWidth={3}
                        zoomable
                        pannable
                        position="bottom-left"
                        nodeColor={(node) => {
                          switch (node.data?.type) {
                            case "api":
                              return "#93c5fd";
                            case "function":
                              return "#d8b4fe";
                            case "trigger":
                              return "#fcd34d";
                            case "data":
                              return "#86efac";
                            case "ai":
                              return "#a5b4fc";
                            case "chatTrigger":
                              return "#fdba74";
                            default:
                              return "#e2e8f0";
                          }
                        }}
                      />

                      {/* Fullscreen button only */}
                      <div className="absolute top-4 right-4 z-10">
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => setIsFullscreen(!isFullscreen)}
                          title={
                            isFullscreen ? "Exit fullscreen" : "Fullscreen"
                          }
                        >
                          {isFullscreen ? (
                            <Minimize2 className="h-4 w-4" />
                          ) : (
                            <Maximize2 className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </ReactFlow>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Select an execution to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
