import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Input } from "@/design-system/ui/input";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Separator } from "@/design-system/ui/separator";
import { Tabs, TabsList, TabsTrigger } from "@/design-system/ui/tabs";
import { cn } from "@/lib/utils";
import ChatMessage, {
  ChatMessageProps,
} from "@features/shared/components/chat-message";
import ChatInput, { Attachment } from "@features/shared/components/chat-input";
import TopNavigation from "@features/shared/components/top-navigation";
import {
  ArrowUpRight,
  CheckCircle2,
  Download,
  ExternalLink,
  Flag,
  MessageCircle,
  Play,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

interface WorkflowRunStep {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed";
  duration: string;
  summary?: string;
}

interface WorkflowRunSummary {
  id: string;
  status: "running" | "completed" | "failed" | "paused";
  startedAt: string;
  completedAt?: string;
  environment: "development" | "staging" | "production";
  tokenUsage: {
    prompt: number;
    completion: number;
    total: number;
  };
  latencyMs: number;
  steps: WorkflowRunStep[];
}

interface ChatThread {
  id: string;
  title: string;
  workflowName: string;
  status: "active" | "resolved" | "handoff";
  updatedAt: string;
  lastMessageSnippet: string;
  tags: string[];
  participants: {
    user: { id: string; name: string; avatar: string };
    ai: { id: string; name: string; avatar: string };
  };
  messages: ChatMessageProps[];
  runs: WorkflowRunSummary[];
  linkedDocs: Array<{ id: string; title: string; href: string }>;
}

const quickPrompts = [
  {
    label: "Summarize last run",
    message:
      "Summarize the latest workflow execution and highlight any blockers.",
  },
  {
    label: "Share handoff notes",
    message:
      "Prepare production handoff notes with outstanding actions and owners.",
  },
  {
    label: "Generate test prompts",
    message:
      "Create three realistic user prompts that exercise edge cases in this workflow.",
  },
  {
    label: "Security review",
    message:
      "List any security or compliance considerations before this flow ships to production.",
  },
];

const threadSeed: ChatThread[] = [
  {
    id: "thread-customer-onboarding",
    title: "Customer onboarding concierge",
    workflowName: "Customer Onboarding Companion",
    status: "handoff",
    updatedAt: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
    lastMessageSnippet:
      "Need final confirmation on the Salesforce sync before launch.",
    tags: ["beta", "production", "handoff"],
    participants: {
      user: {
        id: "user-avery",
        name: "Avery Chen",
        avatar: "https://avatar.vercel.sh/avery",
      },
      ai: {
        id: "ai-orcheo",
        name: "Orcheo Workflow Copilot",
        avatar: "https://avatar.vercel.sh/orcheo",
      },
    },
    messages: [
      {
        id: "msg-1",
        content:
          "Great news! The latest run passed all regression checks. The workflow processed 128 onboarding requests with zero failures.",
        sender: {
          id: "ai-orcheo",
          name: "Orcheo Workflow Copilot",
          avatar: "https://avatar.vercel.sh/orcheo",
          isAI: true,
        },
        timestamp: new Date(Date.now() - 20 * 60 * 1000),
      },
      {
        id: "msg-2",
        content:
          "Can you confirm the Salesforce sync is still scoped to the Sandbox environment? We plan to promote to production after today's handoff.",
        sender: {
          id: "user-avery",
          name: "Avery Chen",
          avatar: "https://avatar.vercel.sh/avery",
        },
        timestamp: new Date(Date.now() - 15 * 60 * 1000),
        isUserMessage: true,
        status: "sent",
      },
      {
        id: "msg-3",
        content:
          "Confirmed. The workflow is currently pointing to the Sandbox instance and the API credentials are scoped to non-production usage only.",
        sender: {
          id: "ai-orcheo",
          name: "Orcheo Workflow Copilot",
          avatar: "https://avatar.vercel.sh/orcheo",
          isAI: true,
        },
        timestamp: new Date(Date.now() - 12 * 60 * 1000),
      },
      {
        id: "msg-4",
        content:
          "Perfect. Generate a production-readiness checklist so we can track the last mile tasks during handoff.",
        sender: {
          id: "user-avery",
          name: "Avery Chen",
          avatar: "https://avatar.vercel.sh/avery",
        },
        timestamp: new Date(Date.now() - 10 * 60 * 1000),
        isUserMessage: true,
        status: "sent",
      },
      {
        id: "msg-5",
        content:
          "Here's a production readiness checklist for the onboarding concierge flow:\n\n1. Validate Salesforce production credentials with scoped permissions.\n2. Schedule launch announcement and support rotation.\n3. Enable observability alerts for critical failure paths.",
        sender: {
          id: "ai-orcheo",
          name: "Orcheo Workflow Copilot",
          avatar: "https://avatar.vercel.sh/orcheo",
          isAI: true,
        },
        timestamp: new Date(Date.now() - 8 * 60 * 1000),
      },
    ],
    runs: [
      {
        id: "run-4827",
        status: "completed",
        startedAt: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
        completedAt: new Date(Date.now() - 38 * 60 * 1000).toISOString(),
        environment: "staging",
        tokenUsage: { prompt: 2350, completion: 1885, total: 4235 },
        latencyMs: 4120,
        steps: [
          {
            id: "step-ingest",
            label: "Collect onboarding details",
            status: "completed",
            duration: "38s",
            summary: "Ingested CSV batch and normalized contact fields.",
          },
          {
            id: "step-ai",
            label: "Draft concierge welcome email",
            status: "completed",
            duration: "22s",
            summary: "Generated personalized welcome copy for 128 users.",
          },
          {
            id: "step-sync",
            label: "Sync to Salesforce Sandbox",
            status: "completed",
            duration: "12s",
            summary:
              "Updated lead records and appended activity timeline entries.",
          },
        ],
      },
    ],
    linkedDocs: [
      {
        id: "doc-1",
        title: "Sandbox credential rotation playbook",
        href: "#",
      },
      {
        id: "doc-2",
        title: "Onboarding concierge release checklist",
        href: "#",
      },
    ],
  },
  {
    id: "thread-support-escalation",
    title: "Support escalation triage",
    workflowName: "Customer Support Escalation",
    status: "active",
    updatedAt: new Date(Date.now() - 55 * 60 * 1000).toISOString(),
    lastMessageSnippet:
      "Monitoring the Zendesk triage queue—automation paused overnight.",
    tags: ["support", "triage"],
    participants: {
      user: {
        id: "user-jordan",
        name: "Jordan Ellis",
        avatar: "https://avatar.vercel.sh/jordan",
      },
      ai: {
        id: "ai-orcheo",
        name: "Orcheo Workflow Copilot",
        avatar: "https://avatar.vercel.sh/orcheo",
      },
    },
    messages: [
      {
        id: "msg-6",
        content:
          "Reminder: the workflow paused escalation dispatch overnight due to rate limits. We should re-enable the trigger after verifying queue depth.",
        sender: {
          id: "ai-orcheo",
          name: "Orcheo Workflow Copilot",
          avatar: "https://avatar.vercel.sh/orcheo",
          isAI: true,
        },
        timestamp: new Date(Date.now() - 60 * 60 * 1000),
      },
      {
        id: "msg-7",
        content:
          "I'll run a health check and resume dispatching once the backlog drops below 25 cases.",
        sender: {
          id: "user-jordan",
          name: "Jordan Ellis",
          avatar: "https://avatar.vercel.sh/jordan",
        },
        timestamp: new Date(Date.now() - 55 * 60 * 1000),
        isUserMessage: true,
        status: "sent",
      },
    ],
    runs: [
      {
        id: "run-3051",
        status: "running",
        startedAt: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
        environment: "production",
        tokenUsage: { prompt: 890, completion: 720, total: 1610 },
        latencyMs: 0,
        steps: [
          {
            id: "step-intake",
            label: "Fetch Zendesk escalations",
            status: "running",
            duration: "--",
          },
          {
            id: "step-route",
            label: "Route to duty manager",
            status: "pending",
            duration: "--",
          },
        ],
      },
    ],
    linkedDocs: [
      {
        id: "doc-3",
        title: "Escalation runbook",
        href: "#",
      },
    ],
  },
  {
    id: "thread-qa-sanity",
    title: "Workflow QA lab",
    workflowName: "End-to-end QA",
    status: "resolved",
    updatedAt: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    lastMessageSnippet:
      "QA session closed—captured findings in the testing doc.",
    tags: ["qa", "regression"],
    participants: {
      user: {
        id: "user-skylar",
        name: "Skylar Patel",
        avatar: "https://avatar.vercel.sh/skylar",
      },
      ai: {
        id: "ai-orcheo",
        name: "Orcheo Workflow Copilot",
        avatar: "https://avatar.vercel.sh/orcheo",
      },
    },
    messages: [
      {
        id: "msg-8",
        content:
          "Documented QA findings and attached the replay artifact. Nothing blocking release.",
        sender: {
          id: "user-skylar",
          name: "Skylar Patel",
          avatar: "https://avatar.vercel.sh/skylar",
        },
        timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000),
        isUserMessage: true,
        status: "sent",
        attachments: [
          {
            id: "attachment-qa-report",
            type: "file",
            name: "qa-session-notes.pdf",
            size: "1.2 MB",
            url: "#",
          },
        ],
      },
      {
        id: "msg-9",
        content:
          "Thanks! I've archived the run artifacts and synced highlights with the release notes.",
        sender: {
          id: "ai-orcheo",
          name: "Orcheo Workflow Copilot",
          avatar: "https://avatar.vercel.sh/orcheo",
          isAI: true,
        },
        timestamp: new Date(Date.now() - 5.5 * 60 * 60 * 1000),
      },
    ],
    runs: [
      {
        id: "run-2219",
        status: "completed",
        startedAt: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString(),
        completedAt: new Date(Date.now() - 6.5 * 60 * 60 * 1000).toISOString(),
        environment: "development",
        tokenUsage: { prompt: 540, completion: 320, total: 860 },
        latencyMs: 2980,
        steps: [
          {
            id: "step-prepare",
            label: "Setup QA fixtures",
            status: "completed",
            duration: "45s",
          },
          {
            id: "step-execute",
            label: "Run regression suite",
            status: "completed",
            duration: "2m 31s",
          },
          {
            id: "step-report",
            label: "Compile QA summary",
            status: "completed",
            duration: "18s",
          },
        ],
      },
    ],
    linkedDocs: [
      {
        id: "doc-4",
        title: "QA regression checklist",
        href: "#",
      },
      {
        id: "doc-5",
        title: "Release notes draft",
        href: "#",
      },
    ],
  },
];

const statusCopy: Record<
  ChatThread["status"],
  { label: string; tone: string }
> = {
  active: {
    label: "Active",
    tone: "bg-blue-100 text-blue-700 dark:bg-blue-400/20 dark:text-blue-200",
  },
  resolved: {
    label: "Resolved",
    tone: "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200",
  },
  handoff: {
    label: "Handoff",
    tone: "bg-purple-100 text-purple-700 dark:bg-purple-400/20 dark:text-purple-200",
  },
};

const runStatusTone: Record<WorkflowRunSummary["status"], string> = {
  running:
    "bg-amber-100 text-amber-700 dark:bg-amber-400/20 dark:text-amber-200",
  completed:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200",
  failed: "bg-red-100 text-red-700 dark:bg-red-400/20 dark:text-red-200",
  paused:
    "bg-slate-200 text-slate-700 dark:bg-slate-500/20 dark:text-slate-200",
};

const environmentTone: Record<WorkflowRunSummary["environment"], string> = {
  development:
    "bg-slate-200 text-slate-700 dark:bg-slate-500/20 dark:text-slate-200",
  staging: "bg-sky-100 text-sky-700 dark:bg-sky-400/20 dark:text-sky-200",
  production:
    "bg-orange-100 text-orange-700 dark:bg-orange-400/20 dark:text-orange-200",
};

function formatRelativeTime(isoDate: string): string {
  const now = Date.now();
  const then = new Date(isoDate).getTime();
  const diffMs = now - then;
  const diffMinutes = Math.round(diffMs / (60 * 1000));
  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
}

function formatMilliseconds(ms: number): string {
  if (!ms) return "--";
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1073741824).toFixed(1)} GB`;
}

export default function ChatLab() {
  const [threads, setThreads] = useState<ChatThread[]>(threadSeed);
  const [selectedThreadId, setSelectedThreadId] = useState<string>(
    threadSeed[0]?.id ?? "",
  );
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "active" | "resolved" | "handoff" | "all"
  >("all");
  const [isAiTyping, setIsAiTyping] = useState(false);

  const filteredThreads = useMemo(() => {
    return threads.filter((thread) => {
      const matchesSearch = thread.title
        .toLowerCase()
        .includes(searchTerm.toLowerCase());
      const matchesStatus =
        statusFilter === "all" ? true : thread.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [threads, searchTerm, statusFilter]);

  useEffect(() => {
    if (!filteredThreads.length) {
      return;
    }

    if (!filteredThreads.some((thread) => thread.id === selectedThreadId)) {
      setSelectedThreadId(filteredThreads[0]?.id ?? selectedThreadId);
    }
  }, [filteredThreads, selectedThreadId]);

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId),
    [threads, selectedThreadId],
  );

  const handleSendMessage = (message: string, attachments: Attachment[]) => {
    if (!selectedThread || (!message.trim() && attachments.length === 0)) {
      return;
    }

    const newMessage: ChatMessageProps = {
      id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      content: message,
      sender: selectedThread.participants.user,
      timestamp: new Date(),
      isUserMessage: true,
      status: "sending",
      attachments: attachments.map((attachment) => ({
        id: attachment.id,
        type: attachment.type,
        name: attachment.file.name,
        url: attachment.previewUrl || URL.createObjectURL(attachment.file),
        size: formatFileSize(attachment.file.size),
      })),
    };

    const threadId = selectedThread.id;

    setThreads((prev) =>
      prev.map((thread) =>
        thread.id === threadId
          ? {
              ...thread,
              updatedAt: new Date().toISOString(),
              lastMessageSnippet: message,
              messages: [...thread.messages, newMessage],
            }
          : thread,
      ),
    );

    setTimeout(() => {
      setThreads((prev) =>
        prev.map((thread) =>
          thread.id === threadId
            ? {
                ...thread,
                messages: thread.messages.map((msg) =>
                  msg.id === newMessage.id ? { ...msg, status: "sent" } : msg,
                ),
              }
            : thread,
        ),
      );
    }, 400);

    setIsAiTyping(true);

    setTimeout(() => {
      const aiResponse: ChatMessageProps = {
        id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        content: generateAiResponse(message, selectedThread),
        sender: {
          ...selectedThread.participants.ai,
          isAI: true,
        },
        timestamp: new Date(),
      };

      setThreads((prev) =>
        prev.map((thread) =>
          thread.id === threadId
            ? {
                ...thread,
                updatedAt: new Date().toISOString(),
                lastMessageSnippet: aiResponse.content.slice(0, 96),
                messages: [...thread.messages, aiResponse],
              }
            : thread,
        ),
      );
      setIsAiTyping(false);
    }, 1400);
  };

  const handleQuickPrompt = (message: string) => {
    handleSendMessage(message, []);
  };

  const handleResolveThread = () => {
    if (!selectedThread) return;
    setThreads((prev) =>
      prev.map((thread) =>
        thread.id === selectedThread.id
          ? {
              ...thread,
              status: "resolved",
              updatedAt: new Date().toISOString(),
            }
          : thread,
      ),
    );
  };

  const latestRun = selectedThread?.runs?.[0];

  return (
    <div className="flex min-h-screen flex-col">
      <TopNavigation
        currentWorkflow={{
          name: selectedThread?.workflowName ?? "Chat Lab",
          path: ["Home", "Workflow Testing"],
        }}
      />

      <div className="flex flex-1 overflow-hidden bg-muted/30">
        <aside className="hidden w-80 shrink-0 border-r bg-background/80 backdrop-blur md:flex md:flex-col">
          <div className="p-4 border-b">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold">Conversations</h2>
                <p className="text-xs text-muted-foreground">
                  Manage workflow chat sessions and handoffs
                </p>
              </div>
              <Button size="icon" variant="outline" asChild>
                <Link to="/workflow-canvas">
                  <Workflow className="h-4 w-4" />
                </Link>
              </Button>
            </div>
            <div className="mt-4 space-y-3">
              <Input
                placeholder="Search conversations"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
              />
              <Tabs
                value={statusFilter}
                onValueChange={(value) =>
                  setStatusFilter(value as typeof statusFilter)
                }
                className="w-full"
              >
                <TabsList className="grid w-full grid-cols-4">
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="active">Active</TabsTrigger>
                  <TabsTrigger value="handoff">Handoff</TabsTrigger>
                  <TabsTrigger value="resolved">Resolved</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>

          <ScrollArea className="flex-1">
            <div className="space-y-2 p-2">
              {filteredThreads.map((thread) => (
                <button
                  key={thread.id}
                  type="button"
                  onClick={() => setSelectedThreadId(thread.id)}
                  className={cn(
                    "w-full rounded-lg border bg-background p-3 text-left transition",
                    selectedThreadId === thread.id
                      ? "border-primary ring-2 ring-primary/20"
                      : "border-transparent hover:border-border",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium leading-tight text-sm">
                      {thread.title}
                    </h3>
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase",
                        statusCopy[thread.status].tone,
                      )}
                    >
                      {statusCopy[thread.status].label}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                    {thread.lastMessageSnippet}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-1">
                    {thread.tags.map((tag) => (
                      <Badge
                        key={tag}
                        variant="outline"
                        className="text-[10px]"
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                    <span>{thread.workflowName}</span>
                    <span>{formatRelativeTime(thread.updatedAt)}</span>
                  </div>
                </button>
              ))}
              {!filteredThreads.length && (
                <Card className="border-dashed bg-background/60 text-center">
                  <CardHeader>
                    <CardTitle className="text-sm">No conversations</CardTitle>
                    <CardDescription className="text-xs">
                      Adjust the filters or start a new chat session.
                    </CardDescription>
                  </CardHeader>
                </Card>
              )}
            </div>
          </ScrollArea>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between border-b bg-background/80 px-6 py-4 backdrop-blur">
            <div>
              <div className="flex items-center gap-3">
                <div className="rounded-full bg-primary/10 p-2">
                  <MessageCircle className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold leading-tight">
                    {selectedThread?.title ?? "Select a conversation"}
                  </h1>
                  <p className="text-xs text-muted-foreground">
                    {selectedThread?.workflowName}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleResolveThread}>
                <CheckCircle2 className="mr-1 h-4 w-4" /> Mark resolved
              </Button>
              <Button variant="outline" size="sm">
                <Download className="mr-1 h-4 w-4" /> Export transcript
              </Button>
            </div>
          </div>

          {selectedThread ? (
            <>
              <ScrollArea className="flex-1 px-6 py-6">
                <div className="mx-auto flex max-w-3xl flex-col gap-4">
                  {selectedThread.messages.map((message) => (
                    <ChatMessage key={message.id} {...message} />
                  ))}

                  {isAiTyping && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
                      The copilot is composing a response…
                    </div>
                  )}
                </div>
              </ScrollArea>

              <div className="border-t bg-background/90 px-6 py-4 shadow-inner">
                <div className="mx-auto max-w-3xl space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {quickPrompts.map((prompt) => (
                      <Button
                        key={prompt.label}
                        variant="secondary"
                        size="sm"
                        onClick={() => handleQuickPrompt(prompt.message)}
                      >
                        <Sparkles className="mr-1 h-4 w-4" />
                        {prompt.label}
                      </Button>
                    ))}
                  </div>
                  <ChatInput
                    onSendMessage={handleSendMessage}
                    placeholder="Ask the copilot to run tests, prep handoffs, or answer workflow questions…"
                  />
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <Card className="max-w-md text-center">
                <CardHeader>
                  <CardTitle>Choose a chat session</CardTitle>
                  <CardDescription>
                    Select a conversation from the left to review workflow runs
                    and collaborate with the copilot.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button asChild>
                    <Link to="/workflow-canvas">
                      <Play className="mr-2 h-4 w-4" /> Launch workflow canvas
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </div>
          )}
        </main>

        {selectedThread && (
          <aside className="hidden w-80 shrink-0 border-l bg-background/80 backdrop-blur xl:flex xl:flex-col">
            <div className="border-b p-4">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Workflow run snapshot
              </h2>
              {latestRun ? (
                <div className="mt-3 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span>Status</span>
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium uppercase",
                        runStatusTone[latestRun.status],
                      )}
                    >
                      {latestRun.status}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-md bg-muted/60 p-2">
                      <p className="text-muted-foreground">Environment</p>
                      <span
                        className={cn(
                          "mt-1 inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium uppercase",
                          environmentTone[latestRun.environment],
                        )}
                      >
                        {latestRun.environment}
                      </span>
                    </div>
                    <div className="rounded-md bg-muted/60 p-2">
                      <p className="text-muted-foreground">Latency</p>
                      <span className="text-sm font-semibold">
                        {formatMilliseconds(latestRun.latencyMs)}
                      </span>
                    </div>
                  </div>
                  <Separator />
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="rounded-md bg-muted/60 p-2">
                      <p className="text-muted-foreground">Prompt</p>
                      <span className="text-sm font-semibold">
                        {latestRun.tokenUsage.prompt.toLocaleString()}
                      </span>
                    </div>
                    <div className="rounded-md bg-muted/60 p-2">
                      <p className="text-muted-foreground">Completion</p>
                      <span className="text-sm font-semibold">
                        {latestRun.tokenUsage.completion.toLocaleString()}
                      </span>
                    </div>
                    <div className="rounded-md bg-muted/60 p-2">
                      <p className="text-muted-foreground">Total</p>
                      <span className="text-sm font-semibold">
                        {latestRun.tokenUsage.total.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-xs text-muted-foreground">
                  No workflow executions captured yet.
                </p>
              )}
            </div>

            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {latestRun && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">
                        Execution timeline
                      </CardTitle>
                      <CardDescription className="text-xs">
                        Track step-by-step progress for the most recent run
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {latestRun.steps.map((step) => (
                        <div
                          key={step.id}
                          className="rounded-md border p-2 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{step.label}</span>
                            <span className="text-[10px] uppercase text-muted-foreground">
                              {step.status}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center justify-between text-muted-foreground">
                            <span>{step.summary ?? "Awaiting output"}</span>
                            <span>{step.duration}</span>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Handoff checklist</CardTitle>
                    <CardDescription className="text-xs">
                      Confirm exit criteria before launch
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-primary" />
                      Credentials rotated and secrets stored in vault
                    </div>
                    <div className="flex items-center gap-2">
                      <Flag className="h-4 w-4 text-primary" />
                      Alerts configured for high-risk failure paths
                    </div>
                    <div className="flex items-center gap-2">
                      <ArrowUpRight className="h-4 w-4 text-primary" />
                      QA evidence attached to release notes
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Linked resources</CardTitle>
                    <CardDescription className="text-xs">
                      Files and docs shared in this conversation
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {selectedThread.linkedDocs.map((doc) => (
                      <Link
                        key={doc.id}
                        to={doc.href}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm hover:bg-muted"
                      >
                        <span>{doc.title}</span>
                        <ExternalLink className="h-4 w-4" />
                      </Link>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </ScrollArea>
          </aside>
        )}
      </div>
    </div>
  );
}

function generateAiResponse(message: string, thread: ChatThread): string {
  const lower = message.toLowerCase();
  if (lower.includes("summary") || lower.includes("summarize")) {
    return `Here's the latest run summary: ${thread.workflowName} executed in ${formatMilliseconds(thread.runs[0]?.latencyMs ?? 0)} with ${thread.runs[0]?.tokenUsage.total.toLocaleString() ?? "--"} total tokens. No regressions detected.`;
  }
  if (lower.includes("handoff")) {
    return "Handoff notes updated. I've tagged outstanding owners and added the checklist to the linked resources.";
  }
  if (lower.includes("security")) {
    return "Security review items: rotate sandbox secrets before production cutover, enable audit logging on credential usage, and confirm SOC2 evidence is archived.";
  }
  if (lower.includes("test")) {
    return "Try these prompts to stress test the workflow: 1) High volume import with 250 leads, 2) Missing CRM account owner, 3) Duplicate email detection edge case.";
  }
  return "I'll log that in the run notes and follow up once the workflow finishes processing.";
}
