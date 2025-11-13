import React from "react";
import { Tabs, TabsContent } from "@/design-system/ui/tabs";

import TopNavigation from "@features/shared/components/top-navigation";
import NodeInspector from "@features/workflow/components/panels/node-inspector";
import WorkflowTabs from "@features/workflow/components/panels/workflow-tabs";
import { CanvasChatBubble } from "@features/chatkit/components/canvas-chat-bubble";

import type {
  CanvasEdge,
  CanvasNode,
  NodeData,
  NodeRuntimeCacheEntry,
} from "@features/workflow/pages/workflow-canvas/helpers/types";
import type { CanvasTabContentProps } from "@features/workflow/pages/workflow-canvas/components/canvas-tab-content";
import type { ExecutionTabContentProps } from "@features/workflow/pages/workflow-canvas/components/execution-tab-content";
import type { ReadinessTabContentProps } from "@features/workflow/pages/workflow-canvas/components/readiness-tab-content";
import type { SettingsTabContentProps } from "@features/workflow/pages/workflow-canvas/components/settings-tab-content";

import { CanvasTabContent } from "@features/workflow/pages/workflow-canvas/components/canvas-tab-content";
import { ExecutionTabContent } from "@features/workflow/pages/workflow-canvas/components/execution-tab-content";
import { TraceTabContent } from "@features/workflow/pages/workflow-canvas/components/trace-tab-content";
import { ReadinessTabContent } from "@features/workflow/pages/workflow-canvas/components/readiness-tab-content";
import { SettingsTabContent } from "@features/workflow/pages/workflow-canvas/components/settings-tab-content";

interface NodeInspectorState {
  selectedNode: CanvasNode | null;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  onClose: () => void;
  onSave: (nodeId: string, data: Partial<NodeData>) => void;
  runtimeCache: Record<string, NodeRuntimeCacheEntry>;
  onCacheRuntime: (nodeId: string, runtime: NodeRuntimeCacheEntry) => void;
}

interface ChatState {
  isChatOpen: boolean;
  chatTitle: string;
  user: {
    id: string;
    name: string;
    avatar: string;
  };
  ai: {
    id: string;
    name: string;
    avatar: string;
  };
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
}

interface WorkflowCanvasLayoutProps {
  topNavigationProps: React.ComponentProps<typeof TopNavigation>;
  tabsProps: {
    activeTab: string;
    onTabChange: (value: string) => void;
    readinessAlertCount: number;
  };
  canvasProps: CanvasTabContentProps;
  executionProps: ExecutionTabContentProps;
  traceProps: React.ComponentProps<typeof TraceTabContent>;
  readinessProps: ReadinessTabContentProps;
  settingsProps: SettingsTabContentProps;
  nodeInspector: NodeInspectorState | null;
  chat: ChatState | null;
}

export function WorkflowCanvasLayout({
  topNavigationProps,
  tabsProps,
  canvasProps,
  executionProps,
  traceProps,
  readinessProps,
  settingsProps,
  nodeInspector,
  chat,
}: WorkflowCanvasLayoutProps) {
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopNavigation {...topNavigationProps} />

      <WorkflowTabs
        activeTab={tabsProps.activeTab}
        onTabChange={tabsProps.onTabChange}
        readinessAlertCount={tabsProps.readinessAlertCount}
      />

      <div className="flex-1 flex flex-col min-h-0">
        <Tabs
          value={tabsProps.activeTab}
          onValueChange={tabsProps.onTabChange}
          className="w-full flex flex-col flex-1 min-h-0"
        >
          <TabsContent
            value="canvas"
            className="flex-1 m-0 p-0 overflow-hidden min-h-0"
          >
            <CanvasTabContent {...canvasProps} />
          </TabsContent>

          <TabsContent
            value="execution"
            className="flex-1 m-0 p-0 overflow-hidden min-h-0"
          >
            <ExecutionTabContent {...executionProps} />
          </TabsContent>

          <TabsContent
            value="trace"
            className="flex-1 m-0 p-4 overflow-hidden min-h-0"
          >
            <TraceTabContent {...traceProps} />
          </TabsContent>

          <TabsContent value="readiness" className="m-0 p-4 overflow-auto">
            <ReadinessTabContent {...readinessProps} />
          </TabsContent>

          <TabsContent value="settings" className="m-0 p-4 overflow-auto">
            <SettingsTabContent {...settingsProps} />
          </TabsContent>
        </Tabs>
      </div>

      {nodeInspector?.selectedNode && (
        <NodeInspector
          node={{
            id: nodeInspector.selectedNode.id,
            type: nodeInspector.selectedNode.type || "default",
            data: nodeInspector.selectedNode.data,
          }}
          nodes={nodeInspector.nodes}
          edges={nodeInspector.edges}
          onClose={nodeInspector.onClose}
          onSave={nodeInspector.onSave}
          runtimeCache={nodeInspector.runtimeCache}
          onCacheRuntime={nodeInspector.onCacheRuntime}
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50"
        />
      )}

      {chat && (
        <CanvasChatBubble
          title={chat.chatTitle}
          user={chat.user}
          ai={chat.ai}
          workflowId={chat.workflowId}
          sessionPayload={{
            workflowId: chat.workflowId,
            workflowLabel: chat.chatTitle,
            chatNodeId: chat.activeChatNodeId,
          }}
          backendBaseUrl={chat.backendBaseUrl}
          getClientSecret={chat.getClientSecret}
          sessionStatus={chat.sessionStatus}
          sessionError={chat.sessionError}
          onRetry={chat.refreshSession}
          onResponseStart={chat.handleChatResponseStart}
          onResponseEnd={chat.handleChatResponseEnd}
          onClientTool={chat.handleChatClientTool}
          onDismiss={chat.handleCloseChat}
          onOpen={() => chat.setIsChatOpen(true)}
          isExternallyOpen={chat.isChatOpen}
        />
      )}
    </div>
  );
}
