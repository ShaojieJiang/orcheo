import React, { useEffect, useMemo, useRef, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import { Checkbox } from "@/design-system/ui/checkbox";
import { Dialog, DialogContent } from "@/design-system/ui/dialog";
import { Input } from "@/design-system/ui/input";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Separator } from "@/design-system/ui/separator";
import { ToggleGroup, ToggleGroupItem } from "@/design-system/ui/toggle-group";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/design-system/ui/tooltip";
import { cn } from "@/lib/utils";
import ChatMessage from "@features/shared/components/chat-message";
import ChatInput, {
  type Attachment,
} from "@features/shared/components/chat-input";
import type { ExecutionStatus } from "@features/workflow/hooks/use-workflow-execution";
import {
  type ChatEnvironment,
  type ChatKitChecklistItem,
  type ChatKitMetrics,
  type ChatKitSession,
} from "@features/shared/components/chatkit/types";
import {
  ArrowUpRight,
  CheckCircle2,
  CircleDashed,
  MessageSquareIcon,
  PinIcon,
  SearchIcon,
  Share2Icon,
  SparklesIcon,
  XIcon,
} from "lucide-react";

interface ChatKitInterfaceProps {
  open: boolean;
  onClose: () => void;
  workflowName: string;
  environment: ChatEnvironment;
  onEnvironmentChange: (environment: ChatEnvironment) => void;
  sessions: ChatKitSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onSendMessage: (
    sessionId: string,
    message: string,
    attachments: Attachment[],
  ) => void;
  onQuickPrompt?: (sessionId: string, prompt: string) => void;
  onToggleChecklistItem?: (
    sessionId: string,
    itemId: string,
    completed: boolean,
  ) => void;
  metrics?: ChatKitMetrics;
  executionStatus?: ExecutionStatus;
  view: "assist" | "handoff";
  onViewChange: (view: "assist" | "handoff") => void;
}

const statusBadgeVariants: Record<string, string> = {
  idle: "secondary",
  connecting: "secondary",
  running: "default",
  completed: "outline",
  error: "destructive",
  cancelled: "secondary",
  handoff: "default",
  "handoff-ready": "success",
  qa: "secondary",
};

const statusLabels: Record<string, string> = {
  idle: "Idle",
  connecting: "Connecting",
  running: "Running",
  completed: "Completed",
  error: "Error",
  cancelled: "Cancelled",
  handoff: "Handoff",
  "handoff-ready": "Ready for handoff",
  qa: "QA review",
};

const getStatusBadgeVariant = (status?: ChatKitSession["status"]) => {
  if (!status) return "secondary" as const;
  return (statusBadgeVariants[status] ?? "secondary") as const;
};

const getStatusLabel = (
  status?: ChatKitSession["status"],
  fallback?: string,
) => {
  if (!status) return fallback ?? "Idle";
  return statusLabels[status] ?? fallback ?? status;
};

const ChecklistItem = ({
  item,
  onToggle,
}: {
  item: ChatKitChecklistItem;
  onToggle?: (next: boolean) => void;
}) => {
  return (
    <label
      className={cn(
        "flex items-start gap-3 rounded-lg border border-border/60 bg-background/40 p-3 transition-all",
        item.completed && "bg-primary/5 border-primary/40",
      )}
    >
      <Checkbox
        checked={item.completed}
        onCheckedChange={(checked) => onToggle?.(Boolean(checked))}
        className="mt-0.5"
      />
      <div className="space-y-1">
        <p className="text-sm font-medium leading-none">{item.label}</p>
        {(item.owner || item.dueDate) && (
          <p className="text-xs text-muted-foreground">
            {item.owner && <span>Owner: {item.owner}</span>}
            {item.owner && item.dueDate && <span className="mx-1">•</span>}
            {item.dueDate && <span>Due {item.dueDate}</span>}
          </p>
        )}
      </div>
    </label>
  );
};

const ConversationList = ({
  sessions,
  activeSessionId,
  onSelectSession,
}: {
  sessions: ChatKitSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
}) => {
  const [search, setSearch] = useState("");

  const filteredSessions = useMemo(() => {
    if (!search.trim()) return sessions;
    const value = search.toLowerCase();
    return sessions.filter((session) => {
      const haystack = [
        session.title,
        session.subtitle,
        session.description,
        ...(session.tags ?? []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(value);
    });
  }, [sessions, search]);

  return (
    <div className="flex h-full w-72 flex-col border-r bg-muted/40">
      <div className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground">
          Conversations
        </h3>
        <div className="mt-3 flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm">
          <SearchIcon className="h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search"
            className="h-auto border-0 p-0 shadow-none focus-visible:ring-0"
          />
        </div>
      </div>
      <Separator />
      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {filteredSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            const status = getStatusLabel(session.status);
            const updatedAtLabel = formatDistanceToNow(
              new Date(session.updatedAt),
              { addSuffix: true },
            );

            return (
              <button
                key={session.id}
                type="button"
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  "group flex w-full flex-col gap-2 rounded-lg border border-transparent px-3 py-2 text-left transition",
                  isActive
                    ? "bg-background shadow-sm border-border"
                    : "hover:bg-background/60",
                )}
              >
                <div className="flex items-center gap-2">
                  {session.pinned && (
                    <PinIcon className="h-3.5 w-3.5 text-primary" />
                  )}
                  <span className="text-sm font-medium truncate">
                    {session.title}
                  </span>
                </div>
                {session.subtitle && (
                  <p className="truncate text-xs text-muted-foreground">
                    {session.subtitle}
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-1">
                  <Badge variant="outline" className="text-[10px] uppercase">
                    {session.environment}
                  </Badge>
                  <Badge
                    variant={getStatusBadgeVariant(session.status)}
                    className="text-[10px]"
                  >
                    {status}
                  </Badge>
                  <span className="text-[11px] text-muted-foreground">
                    {updatedAtLabel}
                  </span>
                </div>
              </button>
            );
          })}
          {filteredSessions.length === 0 && (
            <div className="p-4 text-sm text-muted-foreground">
              No conversations found.
            </div>
          )}
        </div>
      </ScrollArea>
      <Separator />
      <div className="p-4 text-xs text-muted-foreground">
        Conversations auto-sync with your workflow runs.
      </div>
    </div>
  );
};

const MetricCard = ({
  title,
  value,
  description,
  icon: Icon,
}: {
  title: string;
  value: React.ReactNode;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
}) => {
  return (
    <div className="rounded-lg border bg-background p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase text-muted-foreground">
          {title}
        </p>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight">{value}</div>
      {description && (
        <p className="mt-2 text-xs text-muted-foreground">{description}</p>
      )}
    </div>
  );
};

const ChatKitInterface = ({
  open,
  onClose,
  workflowName,
  environment,
  onEnvironmentChange,
  sessions,
  activeSessionId,
  onSelectSession,
  onSendMessage,
  onQuickPrompt,
  onToggleChecklistItem,
  metrics,
  executionStatus,
  view,
  onViewChange,
}: ChatKitInterfaceProps) => {
  const sortedSessions = useMemo(() => {
    return [...sessions].sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });
  }, [sessions]);

  const activeSession = useMemo(() => {
    if (activeSessionId) {
      const match = sortedSessions.find(
        (session) => session.id === activeSessionId,
      );
      if (match) {
        return match;
      }
    }
    return sortedSessions[0] ?? null;
  }, [activeSessionId, sortedSessions]);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [activeSession?.messages]);

  const handleSendMessage = (message: string, attachments: Attachment[]) => {
    if (!activeSession) return;
    onSendMessage(activeSession.id, message, attachments);
  };

  const handleQuickPrompt = (prompt: string) => {
    if (!activeSession) return;
    if (onQuickPrompt) {
      onQuickPrompt(activeSession.id, prompt);
    } else {
      onSendMessage(activeSession.id, prompt, []);
    }
  };

  const handleChecklistToggle = (itemId: string, completed: boolean) => {
    if (!activeSession || !onToggleChecklistItem) return;
    onToggleChecklistItem(activeSession.id, itemId, completed);
  };

  const tokenStats = metrics?.tokens ?? activeSession?.tokenEstimate;
  const statusLabel = getStatusLabel(
    activeSession?.status ?? executionStatus,
    executionStatus ? getStatusLabel(executionStatus) : undefined,
  );

  return (
    <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
      <DialogContent className="max-w-6xl w-[92vw] h-[90vh] overflow-hidden p-0">
        <div className="flex h-full">
          <ConversationList
            sessions={sortedSessions}
            activeSessionId={activeSession?.id ?? null}
            onSelectSession={onSelectSession}
          />
          <div className="flex flex-1 flex-col bg-background">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/30 px-6 py-4">
              <div className="min-w-0">
                <p className="text-xs uppercase text-muted-foreground">
                  {workflowName}
                </p>
                <h2 className="text-xl font-semibold leading-tight">
                  {activeSession?.title ?? "Chat"}
                </h2>
                {activeSession?.subtitle && (
                  <p className="truncate text-sm text-muted-foreground">
                    {activeSession.subtitle}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <ToggleGroup
                  type="single"
                  value={view}
                  onValueChange={(next) =>
                    next && onViewChange(next as "assist" | "handoff")
                  }
                  className="rounded-lg border bg-background"
                >
                  <ToggleGroupItem value="assist" className="px-3 py-1 text-sm">
                    Assist
                  </ToggleGroupItem>
                  <ToggleGroupItem
                    value="handoff"
                    className="px-3 py-1 text-sm"
                  >
                    Handoff
                  </ToggleGroupItem>
                </ToggleGroup>
                <Select
                  value={environment}
                  onValueChange={(value) =>
                    onEnvironmentChange(value as ChatEnvironment)
                  }
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Select env" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="production">Production</SelectItem>
                  </SelectContent>
                </Select>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="outline" size="icon">
                        <Share2Icon className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Share session</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <Button variant="ghost" size="icon" onClick={onClose}>
                  <XIcon className="h-5 w-5" />
                </Button>
              </div>
            </div>

            <div className="border-b bg-muted/40 px-6 py-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <MetricCard
                  title="Session status"
                  value={statusLabel}
                  description="Tracks the latest workflow execution state"
                  icon={CircleDashed}
                />
                <MetricCard
                  title="Token usage"
                  value={
                    tokenStats
                      ? `${tokenStats.total.toLocaleString()} tokens`
                      : "—"
                  }
                  description={
                    tokenStats
                      ? `Prompt ${tokenStats.prompt.toLocaleString()} • Completion ${tokenStats.completion.toLocaleString()}`
                      : "Live tokens will appear after a run"
                  }
                  icon={SparklesIcon}
                />
                <MetricCard
                  title="Updated"
                  value={
                    activeSession
                      ? formatDistanceToNow(new Date(activeSession.updatedAt), {
                          addSuffix: true,
                        })
                      : "—"
                  }
                  description="Sessions auto-refresh with run history"
                  icon={ArrowUpRight}
                />
              </div>
            </div>

            <div className="flex-1 overflow-hidden">
              <div className="flex h-full flex-col">
                <ScrollArea className="flex-1 px-6 py-4">
                  <div className="space-y-3">
                    {activeSession?.messages?.length ? (
                      activeSession.messages.map((message) => (
                        <ChatMessage key={message.id} {...message} />
                      ))
                    ) : (
                      <div className="flex h-full flex-col items-center justify-center rounded-lg border border-dashed p-6 text-center text-muted-foreground">
                        <MessageSquareIcon className="mb-2 h-8 w-8" />
                        <p>No messages yet</p>
                        <p className="text-sm">
                          Start the conversation to trigger this workflow.
                        </p>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                </ScrollArea>

                <div className="border-t bg-muted/30">
                  <div className="flex flex-wrap items-center gap-2 px-6 py-3">
                    {activeSession?.quickPrompts?.map((prompt) => (
                      <Button
                        key={prompt}
                        variant="outline"
                        size="sm"
                        className="rounded-full"
                        onClick={() => handleQuickPrompt(prompt)}
                      >
                        <SparklesIcon className="mr-1 h-3.5 w-3.5" />
                        {prompt}
                      </Button>
                    ))}
                  </div>
                  <ChatInput
                    onSendMessage={handleSendMessage}
                    placeholder="Ask the workflow to test, debug, or hand off"
                    className="border-t bg-background"
                  />
                </div>
              </div>
            </div>

            {view === "handoff" && activeSession?.handoffChecklist && (
              <div className="border-t bg-muted/30 px-6 py-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-primary" />
                  <h3 className="text-sm font-semibold uppercase text-muted-foreground">
                    Handoff checklist
                  </h3>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {activeSession.handoffChecklist.map((item) => (
                    <ChecklistItem
                      key={item.id}
                      item={item}
                      onToggle={(next) => handleChecklistToggle(item.id, next)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ChatKitInterface;
