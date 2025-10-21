import { useEffect, useMemo, useRef } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { XIcon } from "lucide-react";

import { Button } from "@/design-system/ui/button";
import { cn } from "@/lib/utils";
import { buildBackendHttpUrl } from "@lib/config";

export interface WorkflowChatKitPanelProps {
  open: boolean;
  onClose: () => void;
  workflowId?: string | null;
  workflowName: string;
  nodeId?: string | null;
  title: string;
  className?: string;
}

const PANEL_BASE_CLASSES =
  "fixed bottom-4 right-4 z-50 flex h-[520px] w-80 flex-col rounded-lg border bg-background shadow-lg sm:w-96";

const PANEL_BODY_CLASSES = "flex-1 overflow-hidden";

function WorkflowChatUnavailable({
  title,
  workflowName,
  onClose,
  message,
  className,
}: {
  title: string;
  workflowName: string;
  onClose: () => void;
  message: string;
  className?: string;
}) {
  return (
    <div className={cn(PANEL_BASE_CLASSES, className)}>
      <div className="flex items-center justify-between border-b p-3">
        <div>
          <h3 className="font-medium">{title}</h3>
          <p className="text-xs text-muted-foreground">
            {workflowName
              ? `Messages run ${workflowName}`
              : "Messages run this workflow."}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onClose}
        >
          <XIcon className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-center text-sm text-muted-foreground">
        <p>{message}</p>
      </div>
    </div>
  );
}

export function WorkflowChatKitPanel({
  open,
  onClose,
  workflowId,
  workflowName,
  nodeId,
  title,
  className,
}: WorkflowChatKitPanelProps) {
  const fetchSupported = typeof fetch === "function";
  const backendUrl = useMemo(() => buildBackendHttpUrl("/api/chatkit"), []);

  const fetchWithHeaders = useMemo(() => {
    if (!workflowId || !fetchSupported) {
      return async () => {
        throw new Error("Chat backend is not available.");
      };
    }

    return async (url: string, options: RequestInit = {}) => {
      const headers = new Headers(options.headers ?? {});
      headers.set("X-Orcheo-Workflow-Id", workflowId);
      if (nodeId) {
        headers.set("X-Orcheo-Node-Id", nodeId);
      }
      headers.set("X-Orcheo-Chat-Actor", "canvas-chat");
      headers.set("X-Orcheo-Chat-Label", title);
      if (workflowName) {
        headers.set("X-Orcheo-Workflow-Name", workflowName);
      }

      return fetch(url, { ...options, headers });
    };
  }, [workflowId, fetchSupported, nodeId, title, workflowName]);

  const previousNodeRef = useRef<string | null>(null);

  const { control, focusComposer, setThreadId, fetchUpdates } = useChatKit({
    api: {
      url: backendUrl,
      fetch: fetchWithHeaders,
    },
    header: {
      enabled: true,
      title: { text: title },
    },
    startScreen: {
      enabled: true,
      title: `Test ${title}`,
      subtitle: workflowName
        ? `Messages run “${workflowName}”.`
        : "Messages run this workflow.",
    },
    history: {
      enabled: true,
    },
    theme: {
      colorScheme: "light",
      radius: "round",
    },
    composer: {
      placeholder: "Describe what you want this workflow to handle…",
    },
  });

  useEffect(() => {
    if (!open || !fetchSupported || !workflowId) {
      previousNodeRef.current = nodeId ?? null;
      return;
    }

    const resetThread = previousNodeRef.current !== nodeId;
    previousNodeRef.current = nodeId ?? null;
    if (resetThread) {
      void setThreadId(null);
    }
    void focusComposer();
    void fetchUpdates();
  }, [
    open,
    fetchSupported,
    workflowId,
    nodeId,
    setThreadId,
    focusComposer,
    fetchUpdates,
  ]);

  if (!open) {
    return null;
  }

  if (!fetchSupported) {
    return (
      <WorkflowChatUnavailable
        title={title}
        workflowName={workflowName}
        onClose={onClose}
        className={className}
        message="The Fetch API is not available in this environment."
      />
    );
  }

  if (!workflowId) {
    return (
      <WorkflowChatUnavailable
        title={title}
        workflowName={workflowName}
        onClose={onClose}
        className={className}
        message="Save the workflow to generate an identifier before testing chat triggers."
      />
    );
  }

  return (
    <div className={cn(PANEL_BASE_CLASSES, className)}>
      <div className="flex items-center justify-between border-b p-3">
        <div>
          <h3 className="font-medium">{title}</h3>
          <p className="text-xs text-muted-foreground">
            {workflowName
              ? `Messages run ${workflowName}`
              : "Messages run this workflow."}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onClose}
        >
          <XIcon className="h-4 w-4" />
        </Button>
      </div>
      <div className={PANEL_BODY_CLASSES}>
        <ChatKit control={control} className="h-full" />
      </div>
    </div>
  );
}

export default WorkflowChatKitPanel;
