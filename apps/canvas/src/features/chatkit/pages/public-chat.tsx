import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
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
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Skeleton } from "@/design-system/ui/skeleton";
import { getBackendBaseUrl } from "@/lib/config";
import { cn } from "@/lib/utils";
import {
  ApiRequestError,
  fetchWorkflow,
} from "@features/workflow/lib/workflow-storage-api";
import type { ApiWorkflow } from "@features/workflow/lib/workflow-storage.types";
import { PublicChatWidget } from "@features/chatkit/components/public-chat-widget";
import type { PublishHttpError } from "@features/chatkit/lib/chatkit-client";

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
  const [searchParams, setSearchParams] = useSearchParams();
  const [tokenInput, setTokenInput] = useState("");
  const [activeToken, setActiveToken] = useState<string | null>(null);
  const [chatError, setChatError] = useState<PublishHttpError | null>(null);
  const [rateLimitError, setRateLimitError] = useState<PublishHttpError | null>(
    null,
  );
  const [isChatReady, setIsChatReady] = useState(false);
  const backendBaseUrl = useMemo(() => getBackendBaseUrl(), []);

  useEffect(() => {
    setTokenInput("");
    setActiveToken(null);
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

  useEffect(() => {
    const tokenFromQuery = searchParams.get("token");
    if (!tokenFromQuery) {
      return;
    }
    setTokenInput(tokenFromQuery);
    setActiveToken(tokenFromQuery);

    const next = new URLSearchParams(searchParams);
    next.delete("token");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    setIsChatReady(false);
    if (!activeToken) {
      return;
    }
    setChatError(null);
    setRateLimitError(null);
  }, [activeToken]);

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
      `Hi,%0A%0ACould you share a fresh publish token for workflow "${workflowState.workflow.name}" (${workflowState.workflow.id})?%0A%0ALink: ${link}%0A`,
    );
    return `mailto:?subject=${subject}&body=${body}`;
  }, [workflowState]);

  const requireLogin =
    workflowState.status === "ready" && workflowState.workflow.require_login;

  const handleActivateToken = () => {
    if (!tokenInput.trim()) {
      return;
    }
    setActiveToken(tokenInput.trim());
    setChatError(null);
    setRateLimitError(null);
  };

  const handleResetToken = () => {
    setActiveToken(null);
    setTokenInput("");
    setChatError(null);
    setRateLimitError(null);
  };

  const handleChatHttpError = (error: PublishHttpError) => {
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
    if (
      error.code === "chatkit.auth.invalid_publish_token" ||
      error.status === 401 ||
      error.status === 403
    ) {
      setChatError({
        ...error,
        message:
          "This publish token is invalid, expired, or was revoked. Ask the workflow owner for a fresh token.",
      });
      setTokenInput("");
      setActiveToken(null);
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

  const renderLeftColumn = () => {
    if (workflowState.status === "loading") {
      return (
        <Card className="bg-slate-950/40 border-slate-800">
          <CardHeader className="space-y-2">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-1/3" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      );
    }

    if (workflowState.status === "error") {
      return (
        <Card className="bg-slate-950/40 border-slate-800">
          <CardHeader>
            <CardTitle>Workflow unavailable</CardTitle>
            <CardDescription>{workflowState.message}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full" variant="secondary">
              <Link to="/">Back to Canvas</Link>
            </Button>
          </CardContent>
        </Card>
      );
    }

    return (
      <Card className="bg-slate-950/40 border-slate-800 text-left space-y-4">
        <CardHeader className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-xl text-white">
              {workflowState.workflow.name}
            </CardTitle>
            <Badge
              variant="outline"
              className="border-green-500 text-green-300"
            >
              Public
            </Badge>
            {requireLogin && (
              <Badge
                variant="outline"
                className="border-orange-500 text-orange-300"
              >
                Login required
              </Badge>
            )}
          </div>
          <CardDescription className="text-slate-300">
            Paste a publish token to start a ChatKit session for this workflow.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="publish-token">Publish token</Label>
            <Input
              id="publish-token"
              type="password"
              autoComplete="off"
              spellCheck={false}
              inputMode="text"
              placeholder="Paste token from workflow owner"
              value={tokenInput}
              onChange={(event) => setTokenInput(event.currentTarget.value)}
              className="bg-slate-900 border-slate-700"
            />
            <p className="text-xs text-slate-400">
              Tokens never leave this page and are cleared if you refresh or
              close the tab.
            </p>
            <div className="flex gap-2">
              <Button
                className="flex-1"
                disabled={!tokenInput.trim()}
                onClick={handleActivateToken}
              >
                Use token
              </Button>
              {activeToken && (
                <Button variant="ghost" onClick={handleResetToken}>
                  Reset
                </Button>
              )}
            </div>
          </div>
          {requireLogin && (
            <Alert className="bg-amber-500/10 border-amber-500/50 text-amber-100">
              <AlertTitle>Login may be required</AlertTitle>
              <AlertDescription>
                The workflow owner requires OAuth login before chatting. Use the
                button below if you are not already signed in.
              </AlertDescription>
              <Button asChild size="sm" variant="secondary" className="mt-3">
                <Link to="/login">Sign in</Link>
              </Button>
            </Alert>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderChatColumn = () => {
    if (workflowState.status === "loading") {
      return (
        <Card className="border-slate-800 bg-slate-950/40">
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
        <Card className="border-slate-800 bg-slate-950/40">
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
      : activeToken
        ? { text: "Initializing", className: "border-cyan-500 text-cyan-300" }
        : {
            text: "Awaiting token",
            className: "border-slate-600 text-slate-300",
          };

    return (
      <Card className="border-slate-800 bg-slate-950/40">
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-white">
              Chat with “{workflowName || workflowState.workflow.name}”
            </CardTitle>
            <Badge
              variant="outline"
              className={cn("text-xs", badgeTone.className)}
            >
              {badgeTone.text}
            </Badge>
          </div>
          <CardDescription className="text-slate-300">
            Provide a valid publish token to mount the ChatKit widget below.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {rateLimitError && (
            <Alert className="bg-amber-500/10 border-amber-500/50 text-amber-100">
              <AlertTitle>Slow down for a moment</AlertTitle>
              <AlertDescription>
                {rateLimitError.message ||
                  "Too many requests were sent for this publish token. Please wait before retrying."}
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
                <Button onClick={handleResetToken}>Paste new token</Button>
                <Button asChild variant="outline">
                  <a href={contactHref}>Contact owner</a>
                </Button>
              </div>
            </div>
          ) : activeToken ? (
            <div className="relative min-h-[520px]">
              {!isChatReady && (
                <div className="absolute inset-0 flex flex-col gap-4 rounded-lg border border-slate-800 bg-slate-950/80 p-6">
                  <Skeleton className="h-10 w-1/2 self-center" />
                  <Skeleton className="h-full w-full" />
                </div>
              )}
              <div
                className={cn(
                  "h-[520px] w-full rounded-lg border border-slate-800 bg-slate-950/80",
                  isChatReady ? "opacity-100" : "opacity-0",
                  "transition-opacity duration-200",
                )}
              >
                <PublicChatWidget
                  key={`${workflowState.workflow.id}-${activeToken}`}
                  workflowId={workflowState.workflow.id}
                  workflowName={workflowState.workflow.name}
                  publishToken={activeToken}
                  backendBaseUrl={backendBaseUrl}
                  onHttpError={handleChatHttpError}
                  onReady={() => setIsChatReady(true)}
                />
              </div>
            </div>
          ) : (
            <div className="flex min-h-[420px] flex-col items-center justify-center space-y-4 rounded-lg border border-dashed border-slate-800 bg-slate-950/60 px-6 text-center text-slate-400">
              <p>
                Provide a publish token to unlock the public chat experience for
                this workflow. Tokens stay in-memory for this tab only.
              </p>
              <Button
                variant="outline"
                onClick={() => {
                  if (typeof document === "undefined") {
                    return;
                  }
                  document.getElementById("publish-token")?.focus();
                }}
              >
                Paste token
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-6xl px-4 py-10 lg:py-14">
        <div className="flex flex-col gap-3">
          <p className="text-sm uppercase tracking-wide text-slate-400">
            Orcheo ChatKit
          </p>
          <h1 className="text-3xl md:text-4xl font-semibold">
            Share workflows through a secure public chat page
          </h1>
          <p className="text-slate-300 max-w-3xl">
            Only published workflows can be accessed here. Share the page link +
            publish token with trusted testers and rotate the token anytime from
            the Orcheo CLI.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[360px,1fr] mt-10">
          {renderLeftColumn()}
          {renderChatColumn()}
        </div>
      </div>
    </div>
  );
}
