import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Skeleton } from "@/design-system/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/design-system/ui/toggle-group";
import { getBackendBaseUrl } from "@/lib/config";
import { cn } from "@/lib/utils";
import type { Theme } from "@/lib/theme";
import { useThemePreferences } from "@features/account/components/use-theme-preferences";
import {
  ApiRequestError,
  fetchWorkflow,
} from "@features/workflow/lib/workflow-storage-api";
import type { ApiWorkflow } from "@features/workflow/lib/workflow-storage.types";
import { PublicChatWidget } from "@features/chatkit/components/public-chat-widget";
import type { PublicChatHttpError } from "@features/chatkit/lib/chatkit-client";

type WorkflowState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; workflow: ApiWorkflow };

export default function PublicChatPage() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const [workflowState, setWorkflowState] = useState<WorkflowState>({
    status: workflowId ? "loading" : "error",
    ...(workflowId ? {} : { message: "Workflow identifier missing from URL." }),
  });
  const [chatError, setChatError] = useState<PublicChatHttpError | null>(null);
  const [rateLimitError, setRateLimitError] =
    useState<PublicChatHttpError | null>(null);
  const [isChatReady, setIsChatReady] = useState(false);
  const backendBaseUrl = useMemo(() => getBackendBaseUrl(), []);

  useEffect(() => {
    setChatError(null);
    setRateLimitError(null);
    setIsChatReady(false);
  }, [workflowId]);

  useEffect(() => {
    if (!workflowId) {
      return;
    }
    let cancelled = false;
    setWorkflowState({ status: "loading" });

    fetchWorkflow(workflowId)
      .then((workflow) => {
        if (cancelled) {
          return;
        }
        if (!workflow) {
          setWorkflowState({
            status: "error",
            message: "This workflow does not exist or is no longer available.",
          });
          return;
        }
        if (!workflow.is_public) {
          setWorkflowState({
            status: "error",
            message:
              "This workflow is private. Ask the owner to republish it before trying again.",
          });
          return;
        }
        setWorkflowState({ status: "ready", workflow });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        if (error instanceof ApiRequestError) {
          const message =
            error.status >= 500
              ? "The workflow service is unavailable. Please try again later."
              : "Unable to load workflow metadata.";
          setWorkflowState({ status: "error", message });
          return;
        }
        setWorkflowState({
          status: "error",
          message: "Unexpected error while loading workflow metadata.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  const workflowName = useMemo(() => {
    if (workflowState.status !== "ready") {
      return "";
    }
    return workflowState.workflow.name;
  }, [workflowState]);

  const contactHref = useMemo(() => {
    if (workflowState.status !== "ready") {
      return "mailto:?subject=Orcheo%20workflow%20access";
    }
    const subject = encodeURIComponent(
      `Request access to ${workflowState.workflow.name}`,
    );
    const link = typeof window !== "undefined" ? window.location.href : "";
    const body = encodeURIComponent(
      `Hi,%0A%0ACould you confirm access for workflow "${workflowState.workflow.name}" (${workflowState.workflow.id})?%0A%0ALink: ${link}%0A`,
    );
    return `mailto:?subject=${subject}&body=${body}`;
  }, [workflowState]);

  const handleChatHttpError = (error: PublicChatHttpError) => {
    if (error.status === 429 || error.code?.startsWith("chatkit.rate_limit")) {
      setRateLimitError(error);
      return;
    }
    if (error.code === "chatkit.auth.oauth_required") {
      setChatError({
        ...error,
        message:
          "OAuth login is required before this workflow can be used. Sign in and try again.",
      });
      setIsChatReady(false);
      return;
    }
    if (error.status === 401 || error.status === 403) {
      setChatError({
        ...error,
        message:
          "You do not have access to this workflow yet. Ask the owner to confirm it is still published.",
      });
      setIsChatReady(false);
      return;
    }
    setChatError({
      ...error,
      message:
        error.message ||
        "ChatKit could not start this conversation. Please try again shortly.",
    });
    setIsChatReady(false);
  };

  const renderChatColumn = () => {
    if (workflowState.status === "loading") {
      return (
        <Card className="border-slate-200 bg-white/90 dark:border-slate-800 dark:bg-slate-950/40">
          <CardHeader>
            <Skeleton className="h-6 w-48" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-[420px] w-full" />
          </CardContent>
        </Card>
      );
    }

    if (workflowState.status === "error") {
      return (
        <Card className="border-slate-200 bg-white/90 dark:border-slate-800 dark:bg-slate-950/40">
          <CardHeader>
            <CardTitle>Chat unavailable</CardTitle>
            <CardDescription>
              We cannot open a ChatKit session until the workflow loads.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="secondary">
              <Link to="/">Return home</Link>
            </Button>
          </CardContent>
        </Card>
      );
    }

    const badgeTone = isChatReady
      ? { text: "Connected", className: "border-emerald-500 text-emerald-300" }
      : {
          text: "Connecting",
          className: "border-cyan-500 text-cyan-300",
        };

    return (
      <Card className="border-slate-200 bg-white/90 dark:border-slate-800 dark:bg-slate-950/40">
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-slate-900 dark:text-white">
              Chat with “{workflowName || workflowState.workflow.name}”
            </CardTitle>
            <Badge
              variant="outline"
              className={cn("text-xs", badgeTone.className)}
            >
              {badgeTone.text}
            </Badge>
          </div>
          <CardDescription className="text-slate-600 dark:text-slate-300">
            Chat sessions open automatically for published workflows unless the
            owner requires OAuth login.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {rateLimitError && (
            <Alert className="bg-amber-500/10 border-amber-500/50 text-amber-100">
              <AlertTitle>Slow down for a moment</AlertTitle>
              <AlertDescription>
                {rateLimitError.message ||
                  "Too many requests were sent for this workflow. Please wait before retrying."}
              </AlertDescription>
              <div className="mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  className="text-amber-100 border-amber-400/60"
                  onClick={() => setRateLimitError(null)}
                >
                  Dismiss
                </Button>
              </div>
            </Alert>
          )}

          {chatError ? (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-6 text-center space-y-4">
              <p className="font-medium text-red-100">{chatError.message}</p>
              <div className="flex flex-wrap justify-center gap-3">
                <Button asChild variant="outline">
                  <a href={contactHref}>Contact owner</a>
                </Button>
              </div>
            </div>
          ) : (
            <div className="relative min-h-[520px]">
              {!isChatReady && (
                <div className="absolute inset-0 flex flex-col gap-4 rounded-lg border border-slate-200 bg-white/90 p-6 dark:border-slate-800 dark:bg-slate-950/80">
                  <Skeleton className="h-10 w-1/2 self-center" />
                  <Skeleton className="h-full w-full" />
                </div>
              )}
              <div
                className={cn(
                  "h-[520px] w-full rounded-lg border border-slate-200 bg-white/90 dark:border-slate-800 dark:bg-slate-950/80",
                  isChatReady ? "opacity-100" : "opacity-0",
                  "transition-opacity duration-200",
                )}
              >
                <PublicChatWidget
                  key={workflowState.workflow.id}
                  workflowId={workflowState.workflow.id}
                  workflowName={workflowState.workflow.name}
                  backendBaseUrl={backendBaseUrl}
                  onHttpError={handleChatHttpError}
                  onReady={() => setIsChatReady(true)}
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="min-h-screen bg-white text-slate-900 dark:bg-slate-950 dark:text-white">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-10 lg:py-14">
        <div className="flex justify-end">
          <ThemeToggleButtonGroup />
        </div>
        <div className="mt-10 flex flex-1 items-center justify-center">
          <div className="w-full max-w-3xl">{renderChatColumn()}</div>
        </div>
      </div>
    </div>
  );
}

const THEME_OPTIONS: Array<{
  icon: ReactNode;
  label: string;
  value: Theme;
}> = [
  {
    value: "light",
    label: "Light",
    icon: <Sun className="h-4 w-4" />,
  },
  {
    value: "dark",
    label: "Dark",
    icon: <Moon className="h-4 w-4" />,
  },
  {
    value: "system",
    label: "System",
    icon: <Monitor className="h-4 w-4" />,
  },
];

const isThemeValue = (value: string): value is Theme =>
  THEME_OPTIONS.some((option) => option.value === value);

interface ThemeToggleButtonGroupProps {
  className?: string;
}

function ThemeToggleButtonGroup({ className }: ThemeToggleButtonGroupProps) {
  const { theme, setTheme } = useThemePreferences({});

  const handleThemeChange = (value: string) => {
    if (!value || !isThemeValue(value)) {
      return;
    }
    setTheme(value);
  };

  return (
    <ToggleGroup
      type="single"
      value={theme}
      onValueChange={handleThemeChange}
      aria-label="Select display theme"
      className={cn(
        "rounded-full border border-slate-200 bg-white/90 px-1 py-1 shadow-[inset_0_-1px_4px_rgba(15,23,42,0.12)] backdrop-blur-sm dark:border-slate-800 dark:bg-slate-950/70",
        className,
      )}
      variant="default"
      size="default"
    >
      {THEME_OPTIONS.map((option) => (
        <ToggleGroupItem
          key={option.value}
          value={option.value}
          aria-label={`Use ${option.label.toLowerCase()} theme`}
          className="h-9 w-9 rounded-full border border-transparent p-0 text-slate-400 transition-all hover:bg-transparent hover:text-slate-900 dark:text-slate-400 dark:hover:text-white data-[state=on]:border-slate-900/20 data-[state=on]:bg-slate-900 data-[state=on]:text-white data-[state=on]:shadow-[0_4px_12px_rgba(15,23,42,0.3)] dark:data-[state=on]:border-white/30 dark:data-[state=on]:bg-white dark:data-[state=on]:text-slate-900"
        >
          {option.icon}
          <span className="sr-only">{option.label}</span>
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
