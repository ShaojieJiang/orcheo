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
import { VibeAgentSelector } from "./vibe-agent-selector";

const ChatKitSurfaceLazy = lazy(() =>
  import("@features/chatkit/components/chatkit-surface").then((module) => ({
    default: module.ChatKitSurface,
  })),
);

const VIBE_USER = { id: "vibe-user", name: "You", avatar: "" };
const VIBE_AI = { id: "vibe-ai", name: "Orcheo Vibe", avatar: "" };

export function VibeSidebar() {
  const {
    toggleOpen,
    selectedProvider,
    setSelectedProvider,
    readyProviders,
    agentWorkflowId,
    isProvisioning,
    contextString,
  } = useVibe();

  const { getClientSecret, sessionStatus, sessionError, refreshSession } =
    useVibeChat(agentWorkflowId);

  const colorScheme = useColorScheme();
  const hasAgents = readyProviders.length > 0;

  const selectedDisplayName =
    readyProviders.find((p) => p.provider === selectedProvider)?.display_name ??
    "Agent";

  const chatKitOptions = useChatInterfaceOptions({
    chatkitOptions: {
      header: {
        enabled: false,
      },
      composer: {
        placeholder: `Message ${selectedDisplayName}...`,
      },
      startScreen: {
        greeting: `Chat with ${selectedDisplayName} via **Orcheo Vibe**.`,
      },
      theme: buildChatTheme(colorScheme),
    },
    getClientSecret,
    workflowId: agentWorkflowId ?? null,
    sessionPayload: {
      workflowId: agentWorkflowId,
      context: contextString,
    },
    title: `Orcheo Vibe — ${selectedDisplayName}`,
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

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold">Orcheo Vibe</h2>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleOpen}
          className="h-7 w-7"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Close sidebar</span>
        </Button>
      </div>

      {/* Agent selector */}
      <div className="border-b border-border px-4 py-3">
        <VibeAgentSelector
          readyProviders={readyProviders}
          selectedProvider={selectedProvider}
          onSelect={setSelectedProvider}
        />
      </div>

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
        <div className="flex flex-1 flex-col overflow-hidden px-2 py-2">
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
