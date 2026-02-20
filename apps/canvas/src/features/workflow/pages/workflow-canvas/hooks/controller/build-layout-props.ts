import type { ReadinessTabContentProps } from "@features/workflow/pages/workflow-canvas/components/readiness-tab-content";
import type { SettingsTabContentProps } from "@features/workflow/pages/workflow-canvas/components/settings-tab-content";
import type { TraceTabContentProps } from "@features/workflow/pages/workflow-canvas/components/trace-tab-content";
import type { WorkflowTabContentProps } from "@features/workflow/pages/workflow-canvas/components/workflow-tab-content";
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
    onUpdateCredential: WorkflowCanvasResources["credentials"]["handleUpdateCredential"];
    onDeleteCredential: WorkflowCanvasResources["credentials"]["handleDeleteCredential"];
    onRevealCredentialSecret: WorkflowCanvasResources["credentials"]["handleRevealCredentialSecret"];
  };
  tabsProps: {
    activeTab: string;
    onTabChange: (value: string) => void;
    readinessAlertCount: number;
  };
  workflowProps: WorkflowTabContentProps;
  traceProps: TraceTabContentProps;
  readinessProps: ReadinessTabContentProps;
  settingsProps: SettingsTabContentProps;
  chat: {
    isChatOpen: boolean;
    chatTitle: string;
    user: { id: string; name: string; avatar: string };
    ai: { id: string; name: string; avatar: string };
    activeChatNodeId: string | null;
    workflowId: string | null;
    backendBaseUrl: string | null;
    handleChatResponseStart: () => void;
    handleChatResponseEnd: () => void;
    handleChatClientTool: (tool: unknown) => void;
    getClientSecret: (currentSecret: string | null) => Promise<string>;
    refreshSession: () => Promise<string>;
    sessionStatus: "idle" | "loading" | "ready" | "error";
    sessionError: string | null;
    handleCloseChat: () => void;
    setIsChatOpen: (open: boolean) => void;
  } | null;
}

export function buildWorkflowLayoutProps(
  core: WorkflowCanvasCore,
  resources: WorkflowCanvasResources,
  execution: WorkflowCanvasExecution,
): WorkflowLayoutProps {
  const workflowProps: WorkflowTabContentProps = {
    workflowId: core.metadata.currentWorkflowId,
    workflowName: core.metadata.workflowName,
    versions: core.metadata.workflowVersions ?? [],
    isLoading: core.metadata.isWorkflowLoading,
    loadError: core.metadata.workflowLoadError,
    onSaveConfig: resources.saver.handleSaveWorkflowConfig,
  };

  const activeTrace = execution.trace.activeTrace;
  const traceSummary = activeTrace ? summarizeTrace(activeTrace) : undefined;

  const traceProps: TraceTabContentProps = {
    status: execution.trace.status,
    error: execution.trace.error,
    viewerData: execution.trace.viewerData,
    activeViewer: execution.trace.activeTraceViewer,
    onRefresh: () => execution.trace.refresh(),
    isRefreshing: execution.trace.isRefreshing,
    onSelectTrace: (traceId) => core.execution.setActiveExecutionId(traceId),
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
      onUpdateCredential: resources.credentials.handleUpdateCredential,
      onDeleteCredential: resources.credentials.handleDeleteCredential,
      onRevealCredentialSecret:
        resources.credentials.handleRevealCredentialSecret,
    },
    tabsProps: {
      activeTab: core.ui.activeTab,
      onTabChange: core.ui.setActiveTab,
      readinessAlertCount: core.validation.validationErrors.length,
    },
    workflowProps,
    traceProps,
    readinessProps,
    settingsProps,
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
