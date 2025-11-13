import type { CanvasTabContentProps } from "@features/workflow/pages/workflow-canvas/components/canvas-tab-content";
import type { ExecutionTabContentProps } from "@features/workflow/pages/workflow-canvas/components/execution-tab-content";
import type { ReadinessTabContentProps } from "@features/workflow/pages/workflow-canvas/components/readiness-tab-content";
import type { SettingsTabContentProps } from "@features/workflow/pages/workflow-canvas/components/settings-tab-content";
import type { TraceTabContentProps } from "@features/workflow/pages/workflow-canvas/components/trace-tab-content";
import type { WorkflowCanvasCore } from "./use-workflow-canvas-core";
import type { WorkflowCanvasResources } from "./use-workflow-canvas-resources";
import type { WorkflowCanvasExecution } from "./use-workflow-canvas-execution";
import { summarizeTrace } from "@features/workflow/pages/workflow-canvas/helpers/trace";

export interface WorkflowLayoutProps {
  topNavigationProps: {
    currentWorkflow: { name: string; path: string[] };
    credentials: WorkflowCanvasResources["credentials"]["credentials"];
    isCredentialsLoading: boolean;
    onAddCredential: WorkflowCanvasResources["credentials"]["handleAddCredential"];
    onDeleteCredential: WorkflowCanvasResources["credentials"]["handleDeleteCredential"];
  };
  tabsProps: {
    activeTab: string;
    onTabChange: (value: string) => void;
    readinessAlertCount: number;
  };
  canvasProps: CanvasTabContentProps;
  executionProps: ExecutionTabContentProps;
  traceProps: TraceTabContentProps;
  readinessProps: ReadinessTabContentProps;
  settingsProps: SettingsTabContentProps;
  nodeInspector: {
    selectedNode: CanvasTabContentProps["flowHandlers"]["nodes"][number] | null;
    nodes: CanvasTabContentProps["flowHandlers"]["nodes"];
    edges: CanvasTabContentProps["flowHandlers"]["edges"];
    onClose: WorkflowCanvasExecution["inspectorHandlers"]["handleCloseNodeInspector"];
    onSave: WorkflowCanvasExecution["inspectorHandlers"]["handleNodeUpdate"];
    runtimeCache: Record<string, unknown>;
    onCacheRuntime: WorkflowCanvasExecution["inspectorHandlers"]["handleCacheNodeRuntime"];
  } | null;
  chat: {
    isChatOpen: boolean;
    chatTitle: string;
    user: { id: string; name: string; avatar: string };
    ai: { id: string; name: string; avatar: string };
    activeChatNodeId: string | null;
    handleChatResponseStart: () => void;
    handleChatResponseEnd: () => void;
    handleChatClientTool: (tool: unknown) => void;
  } | null;
}

export function buildWorkflowLayoutProps(
  core: WorkflowCanvasCore,
  resources: WorkflowCanvasResources,
  execution: WorkflowCanvasExecution,
): WorkflowLayoutProps {
  const selectedNode =
    core.history.nodes.find((node) => node.id === core.ui.selectedNodeId) ??
    null;

  const canvasProps: CanvasTabContentProps = {
    sidebarCollapsed: core.ui.sidebarCollapsed,
    onToggleSidebar: () =>
      core.ui.setSidebarCollapsed(!core.ui.sidebarCollapsed),
    onAddNode: execution.nodeCreation.handleAddNode,
    reactFlowWrapperRef: core.reactFlowWrapper,
    onDragOver: execution.nodeCreation.onDragOver,
    onDrop: execution.nodeCreation.onDrop,
    edgeHoverContextValue: {
      hoveredEdgeId: core.ui.hoveredEdgeId,
      setHoveredEdgeId: core.ui.setHoveredEdgeId,
    },
    flowHandlers: {
      nodes: core.nodeState.decoratedNodes,
      edges: core.history.edges,
      onNodesChange: core.history.onNodesChange,
      onEdgesChange: core.history.onEdgesChange,
      onConnect: execution.handleConnect,
      onNodeClick: () => {},
      onNodeDoubleClick: (_event, node) => {
        if (node.type !== "startEnd") {
          core.ui.setSelectedNodeId(node.id);
        }
      },
      onEdgeMouseEnter: execution.edgeHoverHandlers.onEnter,
      onEdgeMouseLeave: execution.edgeHoverHandlers.onLeave,
      onInit: (instance) => {
        core.reactFlowInstance.current = instance;
      },
    },
    searchHandlers: {
      isOpen: core.search.isSearchOpen,
      onSearch: core.search.handleSearchNodes,
      onHighlightNext: core.search.handleHighlightNext,
      onHighlightPrevious: core.search.handleHighlightPrevious,
      onClose: core.search.handleCloseSearch,
      matchCount: core.search.searchMatches.length,
      currentMatchIndex: core.search.currentSearchIndex,
      className: "backdrop-blur supports-[backdrop-filter]:bg-background/60",
    },
    controlsHandlers: {
      isRunning: core.execution.isRunning,
      onRun: execution.handleRunWorkflow,
      onPause: execution.handlePauseWorkflow,
      onSave: resources.saver.handleSaveWorkflow,
      onUndo: core.history.handleUndo,
      onRedo: core.history.handleRedo,
      canUndo: core.history.canUndo,
      canRedo: core.history.canRedo,
      onDuplicate: resources.duplicateNodes.handleDuplicateSelectedNodes,
      onExport: resources.fileTransfer.handleExportWorkflow,
      onImport: resources.fileTransfer.handleImportWorkflow,
      onToggleSearch: core.search.handleToggleSearch,
      isSearchOpen: core.search.isSearchOpen,
    },
    fileInputRef: resources.fileTransfer.fileInputRef,
    onFileSelected: resources.fileTransfer.handleWorkflowFileSelected,
    validation: {
      errors: core.validation.validationErrors,
      onDismiss: execution.handleDismissValidation,
      onFix: execution.handleFixValidation,
    },
  };

  const executionProps: ExecutionTabContentProps = {
    executions: core.execution.executions,
    onViewDetails:
      execution.executionHistoryHandlers.handleViewExecutionDetails,
    onRefresh: execution.executionHistoryHandlers.handleRefreshExecutionHistory,
    onCopyToEditor:
      execution.executionHistoryHandlers.handleCopyExecutionToEditor,
    onDelete: execution.executionHistoryHandlers.handleDeleteExecution,
    onRunWorkflow: execution.handleRunWorkflow,
    onPauseWorkflow: execution.handlePauseWorkflow,
    isRunning: core.execution.isRunning,
    activeExecutionId: core.execution.activeExecutionId,
    setActiveExecutionId: core.execution.setActiveExecutionId,
  };

  const activeTrace = execution.trace.activeTrace;
  const traceSummary = activeTrace ? summarizeTrace(activeTrace) : undefined;

  const traceProps: TraceTabContentProps = {
    status: execution.trace.status,
    error: execution.trace.error,
    viewerData: execution.trace.viewerData,
    activeViewer: execution.trace.activeTraceViewer,
    onRefresh: () => execution.trace.refresh(),
    summary: traceSummary,
    lastUpdatedAt: activeTrace?.lastUpdatedAt,
    isLive: Boolean(activeTrace && !activeTrace.isComplete),
  };

  const readinessProps: ReadinessTabContentProps = {
    subworkflows: core.subworkflowState.subworkflows,
    onCreateSubworkflow: execution.handleCreateSubworkflow,
    onInsertSubworkflow: execution.handleInsertSubworkflow,
    onDeleteSubworkflow: execution.handleDeleteSubworkflow,
    validationErrors: core.validation.validationErrors,
    onRunValidation: execution.runPublishValidation,
    onDismissValidation: execution.handleDismissValidation,
    onFixValidation: execution.handleFixValidation,
    isValidating: core.validation.isValidating,
    lastValidationRun: core.validation.lastValidationRun,
  };

  const settingsProps: SettingsTabContentProps = {
    workflowName: core.metadata.workflowName,
    workflowDescription: core.metadata.workflowDescription,
    workflowTags: core.metadata.workflowTags,
    onWorkflowNameChange: core.metadata.setWorkflowName,
    onWorkflowDescriptionChange: core.metadata.setWorkflowDescription,
    onTagsChange: resources.saver.handleTagsChange,
    workflowVersions: core.metadata.workflowVersions ?? [],
    onRestoreVersion: resources.saver.handleRestoreVersion,
    onSaveWorkflow: resources.saver.handleSaveWorkflow,
  };

  return {
    topNavigationProps: {
      currentWorkflow: {
        name: core.metadata.workflowName,
        path: ["Projects", "Workflows", core.metadata.workflowName],
      },
      credentials: resources.credentials.credentials,
      isCredentialsLoading: resources.credentials.isCredentialsLoading,
      onAddCredential: resources.credentials.handleAddCredential,
      onDeleteCredential: resources.credentials.handleDeleteCredential,
    },
    tabsProps: {
      activeTab: core.ui.activeTab,
      onTabChange: core.ui.setActiveTab,
      readinessAlertCount: core.validation.validationErrors.length,
    },
    canvasProps,
    executionProps,
    traceProps,
    readinessProps,
    settingsProps,
    nodeInspector: selectedNode
      ? {
          selectedNode,
          nodes: core.history.nodes,
          edges: core.history.edges,
          onClose: execution.inspectorHandlers.handleCloseNodeInspector,
          onSave: execution.inspectorHandlers.handleNodeUpdate,
          runtimeCache: core.nodeRuntimeCache,
          onCacheRuntime: execution.inspectorHandlers.handleCacheNodeRuntime,
        }
      : null,
    chat: {
      isChatOpen: core.chat.isChatOpen,
      chatTitle: core.chat.chatTitle,
      user: core.user,
      ai: core.ai,
      activeChatNodeId: core.chat.activeChatNodeId,
      workflowId: core.chat.workflowId,
      backendBaseUrl: core.chat.backendBaseUrl,
      handleChatResponseStart: core.chat.handleChatResponseStart,
      handleChatResponseEnd: core.chat.handleChatResponseEnd,
      handleChatClientTool: core.chat.handleChatClientTool,
      getClientSecret: core.chat.getClientSecret,
      refreshSession: core.chat.refreshSession,
      sessionStatus: core.chat.sessionStatus,
      sessionError: core.chat.sessionError,
      handleCloseChat: core.chat.handleCloseChat,
      setIsChatOpen: core.chat.setIsChatOpen,
    },
  };
}
