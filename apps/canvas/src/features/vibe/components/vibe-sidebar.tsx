import { lazy, Suspense, useMemo } from "react";
import { Link } from "react-router-dom";
import { Loader2, Settings, Sparkles, X } from "lucide-react";
import { Button } from "@/design-system/ui/button";
import { Skeleton } from "@/design-system/ui/skeleton";
import { cn } from "@/lib/utils";
import { useVibe } from "@features/vibe/context/vibe-context";
import { useVibeChat } from "@features/vibe/hooks/use-vibe-chat";
import { useChatInterfaceOptions } from "@features/shared/components/chat-interface-options";
import { useColorScheme } from "@/hooks/use-color-scheme";
import { buildChatTheme } from "@features/chatkit/lib/chatkit-theme";
import { buildVibeComposerModels } from "@features/vibe/lib/vibe-models";

const ChatKitSurfaceLazy = lazy(() =>
  import("@features/chatkit/components/chatkit-surface").then((module) => ({
    default: module.ChatKitSurface,
  })),
);

const VIBE_USER = { id: "vibe-user", name: "You", avatar: "" };
const VIBE_AI = { id: "vibe-ai", name: "Orcheo Vibe", avatar: "" };

interface VibeSidebarProps {
  isCollapsed?: boolean;
}

export function VibeSidebar({ isCollapsed = false }: VibeSidebarProps) {
  const {
    toggleOpen,
    readyProviders,
    agentWorkflowId,
    isProvisioning,
    contextString,
  } = useVibe();

  const { getClientSecret, sessionStatus, sessionError, refreshSession } =
    useVibeChat(agentWorkflowId);

  const colorScheme = useColorScheme();
  const hasAgents = readyProviders.length > 0;
  const modelOptions = buildVibeComposerModels(readyProviders);
  const showChatKitHeader = hasAgents && !isCollapsed;

  const chatKitOptions = useChatInterfaceOptions({
    chatkitOptions: {
      header: {
        enabled: showChatKitHeader,
        title: {
          enabled: true,
          text: "Orcheo Vibe",
        },
        rightAction: {
          icon: "close",
          onClick: toggleOpen,
        },
      },
      history: {
        enabled: true,
      },
      composer: {
        placeholder: "Message Orcheo Vibe...",
        ...(modelOptions ? { models: modelOptions } : {}),
      },
      startScreen: {
        greeting: "Vibe with Orcheo",
      },
      theme: buildChatTheme(colorScheme),
    },
    getClientSecret,
    workflowId: agentWorkflowId ?? null,
    sessionPayload: {
      workflowId: agentWorkflowId,
      context: contextString,
    },
    title: "Orcheo Vibe",
    user: VIBE_USER,
    ai: VIBE_AI,
    initialMessages: [],
  });

  const statusView = useMemo(() => {
    if (isProvisioning) {
      return (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <p>Setting up agent workflow...</p>
        </div>
      );
    }

    if (sessionStatus === "loading") {
      return (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <p>Starting chat session...</p>
        </div>
      );
    }

    if (sessionStatus === "error") {
      return (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 text-center text-sm text-muted-foreground">
          <p className="text-destructive">
            {sessionError ?? "Failed to start chat session."}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refreshSession()}
          >
            Retry
          </Button>
        </div>
      );
    }

    return null;
  }, [isProvisioning, sessionStatus, sessionError, refreshSession]);

  if (isCollapsed) {
    return (
      <div className="relative h-full w-0 overflow-visible">
        <button
          type="button"
          onClick={toggleOpen}
          className="absolute left-0 top-40 z-20 flex h-7 w-7 items-center justify-center rounded-full bg-muted text-foreground shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          title="Open Orcheo Vibe"
        >
          <Sparkles
            className={cn(
              "h-4 w-4",
              hasAgents ? "text-primary" : "text-muted-foreground",
            )}
          />
          <span className="sr-only">Open Orcheo Vibe</span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {(!showChatKitHeader || statusView) && (
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4 lg:px-6">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">Orcheo Vibe</h2>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleOpen}
            className="h-8 w-8"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close sidebar</span>
          </Button>
        </div>
      )}

      {/* Content */}
      {!hasAgents ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
          <Settings className="h-8 w-8 text-muted-foreground" />
          <div className="space-y-1">
            <p className="text-sm font-medium">No agents connected</p>
            <p className="text-xs text-muted-foreground">
              Connect an external agent to start using Orcheo Vibe.
            </p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link to="/settings">Go to Settings</Link>
          </Button>
        </div>
      ) : (
        <div className={cn("flex flex-1 flex-col overflow-hidden px-2 py-2")}>
          {statusView}
          {!statusView && agentWorkflowId && (
            <Suspense
              fallback={
                <div className="flex h-full w-full flex-col gap-3">
                  <Skeleton className="h-10 w-1/2 self-center" />
                  <Skeleton className="h-full w-full" />
                </div>
              }
            >
              <ChatKitSurfaceLazy
                options={chatKitOptions}
                className={cn(
                  sessionStatus !== "ready" && "pointer-events-none opacity-50",
                )}
              />
            </Suspense>
          )}
        </div>
      )}
    </div>
  );
}
