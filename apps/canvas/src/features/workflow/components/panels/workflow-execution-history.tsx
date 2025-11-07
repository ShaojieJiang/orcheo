import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import SidebarLayout from "@features/workflow/components/layouts/sidebar-layout";
import NodeInspector from "@features/workflow/components/panels/node-inspector";
import WorkflowExecutionSidebar from "./workflow-execution-sidebar";
import WorkflowExecutionDetails from "./workflow-execution-details";
import {
  useExecutionPagination,
  useSelectedExecution,
} from "./workflow-execution-history.hooks";
import { normaliseNodeStatus } from "./workflow-execution-history.utils";
import type {
  WorkflowExecution,
  WorkflowExecutionHistoryProps,
} from "./workflow-execution-history.types";

const pageSizeOptions = [10, 20, 50];

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
  const { selectedExecution, setSelectedExecution } = useSelectedExecution(
    executions,
    defaultSelectedExecution,
  );
  const {
    page,
    pageSize,
    pageCount,
    totalExecutions,
    currentPageExecutions,
    startOffset,
    endOffset,
    isFirstPage,
    isLastPage,
    changePageSize,
    goToPreviousPage,
    goToNextPage,
  } = useExecutionPagination(executions);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const handleSelectExecution = (execution: WorkflowExecution) => {
    setSelectedExecution(execution);
    setSelectedNodeId(null);
  };

  const selectedNode = useMemo(() => {
    if (!selectedNodeId || !selectedExecution) {
      return null;
    }

    const node = selectedExecution.nodes.find((n) => n.id === selectedNodeId);
    if (!node) {
      return null;
    }

    return {
      id: node.id,
      type: node.type || "default",
      data: {
        type: node.type || "default",
        label: node.name,
        status: normaliseNodeStatus(node.status),
        iconKey: node.iconKey,
        details: node.details,
        ...(node.details || {}),
      },
    };
  }, [selectedNodeId, selectedExecution]);

  const mainContent = (
    <WorkflowExecutionDetails
      execution={selectedExecution}
      isFullscreen={isFullscreen}
      onToggleFullscreen={() => setIsFullscreen((prev) => !prev)}
      onNodeSelect={(nodeId) => setSelectedNodeId(nodeId)}
      onCopyToEditor={onCopyToEditor}
      onDelete={onDelete}
    />
  );

  const sidebar = (
    <WorkflowExecutionSidebar
      totalExecutions={totalExecutions}
      currentPageExecutions={currentPageExecutions}
      selectedExecutionId={selectedExecution?.id}
      page={page}
      pageCount={pageCount}
      pageSize={pageSize}
      pageSizeOptions={pageSizeOptions}
      isFirstPage={isFirstPage}
      isLastPage={isLastPage}
      startOffset={startOffset}
      endOffset={endOffset}
      onSelectExecution={handleSelectExecution}
      onPreviousPage={goToPreviousPage}
      onNextPage={goToNextPage}
      onPageSizeChange={changePageSize}
      onRefresh={onRefresh}
      onViewDetails={onViewDetails}
    />
  );

  const content = (
    <>
      {showList ? (
        <SidebarLayout
          sidebar={sidebar}
          sidebarWidth={sidebarWidth}
          onWidthChange={setSidebarWidth}
          resizable
          minWidth={200}
          maxWidth={500}
          showCollapseButton={false}
        >
          <div className="flex h-full flex-col">{mainContent}</div>
        </SidebarLayout>
      ) : (
        mainContent
      )}

      {selectedNode && (
        <NodeInspector
          node={selectedNode}
          onClose={() => setSelectedNodeId(null)}
          className="absolute left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 transform"
        />
      )}
    </>
  );

  if (!showList) {
    return (
      <div className={cn("flex h-full w-full flex-col", className)}>
        {content}
      </div>
    );
  }

  return <div className={cn("h-full w-full", className)}>{content}</div>;
}
