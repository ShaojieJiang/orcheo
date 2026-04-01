import { useCallback, useEffect, useMemo, useState } from "react";
import { ExternalLink, Loader2, RefreshCw } from "lucide-react";

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
import { Separator } from "@/design-system/ui/separator";
import { Input } from "@/design-system/ui/input";
import {
  getExternalAgentLoginSession,
  getExternalAgents,
  refreshExternalAgents,
  startExternalAgentLogin,
  submitExternalAgentLoginInput,
  type ExternalAgentLoginSession,
  type ExternalAgentLoginSessionState,
  type ExternalAgentProviderName,
  type ExternalAgentProviderState,
  type ExternalAgentProviderStatus,
} from "@/lib/api";

const CONTEXT_URL = "http://localhost:3333/context/sessions";
const PROVIDER_ORDER: ExternalAgentProviderName[] = ["claude_code", "codex"];
const SESSION_TERMINAL_STATES = new Set<ExternalAgentLoginSessionState>([
  "authenticated",
  "failed",
  "timed_out",
]);

type ActiveSessions = Partial<Record<ExternalAgentProviderName, string>>;
type SessionMap = Partial<
  Record<ExternalAgentProviderName, ExternalAgentLoginSession>
>;

function useCopyFeedback() {
  const [copiedValue, setCopiedValue] = useState<string | null>(null);

  const copy = useCallback((text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedValue(text);
    setTimeout(() => setCopiedValue(null), 2000);
  }, []);

  return { copiedValue, copy };
}

const badgeVariantForState = (
  state: ExternalAgentProviderState,
): "default" | "secondary" | "destructive" | "outline" => {
  if (state === "ready") {
    return "default";
  }
  if (state === "error") {
    return "destructive";
  }
  if (state === "needs_login" || state === "not_installed") {
    return "outline";
  }
  return "secondary";
};

const labelForProviderState = (state: ExternalAgentProviderState): string => {
  switch (state) {
    case "checking":
      return "Checking";
    case "installing":
      return "Installing";
    case "not_installed":
      return "Not installed";
    case "needs_login":
      return "Needs login";
    case "authenticating":
      return "Connecting";
    case "ready":
      return "Connected";
    case "error":
      return "Error";
    default:
      return "Unknown";
  }
};

const labelForSessionState = (
  state: ExternalAgentLoginSessionState,
): string => {
  switch (state) {
    case "installing":
      return "Installing runtime";
    case "awaiting_oauth":
      return "Awaiting browser sign-in";
    case "authenticated":
      return "Authenticated";
    case "failed":
      return "Failed";
    case "timed_out":
      return "Timed out";
    default:
      return "Preparing";
  }
};

const isTerminalSessionState = (
  state: ExternalAgentLoginSessionState,
): boolean => SESSION_TERMINAL_STATES.has(state);

const formatTimestamp = (value: string | null): string | null => {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
};

const sortStatuses = (
  providers: ExternalAgentProviderStatus[],
): ExternalAgentProviderStatus[] =>
  [...providers].sort(
    (left, right) =>
      PROVIDER_ORDER.indexOf(left.provider) -
      PROVIDER_ORDER.indexOf(right.provider),
  );

const AgentSettingsTab = () => {
  const [sessionCount, setSessionCount] = useState<number | null>(null);
  const [serverRunning, setServerRunning] = useState(false);
  const [providerStatuses, setProviderStatuses] = useState<
    ExternalAgentProviderStatus[]
  >([]);
  const [loginSessions, setLoginSessions] = useState<SessionMap>({});
  const [activeSessions, setActiveSessions] = useState<ActiveSessions>({});
  const [isLoadingStatuses, setIsLoadingStatuses] = useState(true);
  const [isRefreshingStatuses, setIsRefreshingStatuses] = useState(false);
  const [pendingProvider, setPendingProvider] =
    useState<ExternalAgentProviderName | null>(null);
  const [pendingInputProvider, setPendingInputProvider] =
    useState<ExternalAgentProviderName | null>(null);
  const [sessionInputs, setSessionInputs] = useState<
    Partial<Record<ExternalAgentProviderName, string>>
  >({});
  const [statusError, setStatusError] = useState<string | null>(null);
  const { copiedValue, copy } = useCopyFeedback();

  const syncActiveSessions = useCallback(
    (providers: ExternalAgentProviderStatus[]) => {
      setActiveSessions((current) => {
        const next = { ...current };
        for (const provider of providers) {
          if (provider.active_session_id) {
            next[provider.provider] = provider.active_session_id;
          }
        }
        return next;
      });
    },
    [],
  );

  const loadProviderStatuses = useCallback(async () => {
    try {
      const response = await getExternalAgents();
      const providers = sortStatuses(response.providers);
      setProviderStatuses(providers);
      syncActiveSessions(providers);
      setStatusError(null);
    } catch (error) {
      setStatusError(
        error instanceof Error
          ? error.message
          : "Failed to load external agent status.",
      );
    } finally {
      setIsLoadingStatuses(false);
    }
  }, [syncActiveSessions]);

  const queueStatusRefresh = useCallback(async () => {
    setIsRefreshingStatuses(true);
    try {
      const response = await refreshExternalAgents();
      const providers = sortStatuses(response.providers);
      setProviderStatuses(providers);
      syncActiveSessions(providers);
      setStatusError(null);
    } catch (error) {
      setStatusError(
        error instanceof Error
          ? error.message
          : "Failed to refresh external agent status.",
      );
    } finally {
      setIsRefreshingStatuses(false);
    }
  }, [syncActiveSessions]);

  useEffect(() => {
    let cancelled = false;

    const pollContextBridge = async () => {
      try {
        const response = await fetch(CONTEXT_URL);
        if (!cancelled) {
          const sessions = await response.json();
          setSessionCount(Array.isArray(sessions) ? sessions.length : 0);
          setServerRunning(true);
        }
      } catch {
        if (!cancelled) {
          setSessionCount(null);
          setServerRunning(false);
        }
      }
    };

    void pollContextBridge();
    const interval = setInterval(pollContextBridge, 10_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    void loadProviderStatuses();
    void queueStatusRefresh();
  }, [loadProviderStatuses, queueStatusRefresh]);

  useEffect(() => {
    const interval = setInterval(() => {
      void loadProviderStatuses();
    }, 4_000);
    return () => clearInterval(interval);
  }, [loadProviderStatuses]);

  useEffect(() => {
    const entries = Object.entries(activeSessions) as Array<
      [ExternalAgentProviderName, string]
    >;
    if (entries.length === 0) {
      return;
    }

    let cancelled = false;
    const pollSessions = async () => {
      for (const [provider, sessionId] of entries) {
        try {
          const session = await getExternalAgentLoginSession(sessionId);
          if (cancelled) {
            return;
          }
          setLoginSessions((current) => ({
            ...current,
            [provider]: session,
          }));
          if (isTerminalSessionState(session.state)) {
            setActiveSessions((current) => {
              const next = { ...current };
              delete next[provider];
              return next;
            });
            void loadProviderStatuses();
          }
        } catch (error) {
          if (cancelled) {
            return;
          }
          setStatusError(
            error instanceof Error
              ? error.message
              : "Failed to poll external agent login session.",
          );
          setActiveSessions((current) => {
            const next = { ...current };
            delete next[provider];
            return next;
          });
        }
      }
    };

    void pollSessions();
    const interval = setInterval(() => {
      void pollSessions();
    }, 1_500);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [activeSessions, loadProviderStatuses]);

  const handleConnect = useCallback(
    async (provider: ExternalAgentProviderName) => {
      setPendingProvider(provider);
      try {
        const session = await startExternalAgentLogin(provider);
        setLoginSessions((current) => ({
          ...current,
          [provider]: session,
        }));
        setActiveSessions((current) => ({
          ...current,
          [provider]: session.session_id,
        }));
        setStatusError(null);
        void loadProviderStatuses();
      } catch (error) {
        setStatusError(
          error instanceof Error
            ? error.message
            : "Failed to start the worker login flow.",
        );
      } finally {
        setPendingProvider(null);
      }
    },
    [loadProviderStatuses],
  );

  const handleSubmitSessionInput = useCallback(
    async (provider: ExternalAgentProviderName, sessionId: string) => {
      const inputText = sessionInputs[provider]?.trim();
      if (!inputText) {
        setStatusError("Enter the authentication code before submitting it.");
        return;
      }
      setPendingInputProvider(provider);
      try {
        const session = await submitExternalAgentLoginInput(sessionId, {
          input_text: inputText,
        });
        setLoginSessions((current) => ({
          ...current,
          [provider]: session,
        }));
        setSessionInputs((current) => ({
          ...current,
          [provider]: "",
        }));
        setStatusError(null);
      } catch (error) {
        setStatusError(
          error instanceof Error
            ? error.message
            : "Failed to submit worker login input.",
        );
      } finally {
        setPendingInputProvider(null);
      }
    },
    [sessionInputs],
  );

  const providerCards = useMemo(
    () =>
      providerStatuses.map((provider) => {
        const session =
          loginSessions[provider.provider] &&
          loginSessions[provider.provider]?.session_id ===
            provider.active_session_id
            ? loginSessions[provider.provider]
            : loginSessions[provider.provider];
        const checkedAt = formatTimestamp(provider.checked_at);
        const lastAuthAt = formatTimestamp(provider.last_auth_ok_at);
        const isBusy =
          pendingProvider === provider.provider ||
          provider.state === "checking" ||
          provider.state === "installing" ||
          provider.state === "authenticating";
        const connectLabel =
          provider.state === "not_installed"
            ? "Install and connect"
            : provider.state === "ready"
              ? "Reconnect"
              : "Connect";

        return (
          <Card key={provider.provider} className="border-border/80">
            <CardHeader className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <CardTitle className="text-base">
                    {provider.display_name}
                  </CardTitle>
                  <CardDescription>
                    Worker-scoped OAuth and runtime status for{" "}
                    {provider.display_name}.
                  </CardDescription>
                </div>
                <Badge variant={badgeVariantForState(provider.state)}>
                  {labelForProviderState(provider.state)}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                <span>
                  Version: {provider.resolved_version ?? "Not installed"}
                </span>
                {checkedAt && <span>Checked: {checkedAt}</span>}
                {lastAuthAt && <span>Last auth: {lastAuthAt}</span>}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {provider.detail ??
                  "Canvas will manage the worker-side runtime and OAuth flow."}
              </p>

              {session && (
                <div className="rounded-md border bg-muted/30 p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">
                      {labelForSessionState(session.state)}
                    </Badge>
                    {session.resolved_version && (
                      <span className="text-muted-foreground">
                        Runtime {session.resolved_version}
                      </span>
                    )}
                  </div>
                  {session.detail && (
                    <p className="mt-2 text-muted-foreground">
                      {session.detail}
                    </p>
                  )}
                  {session.auth_url && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <code className="rounded bg-background px-2 py-1 text-xs">
                        {session.auth_url}
                      </code>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          window.open(session.auth_url ?? "", "_blank")
                        }
                      >
                        <ExternalLink className="mr-2 h-3.5 w-3.5" />
                        Open sign-in
                      </Button>
                    </div>
                  )}
                  {session.device_code && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <code className="rounded bg-background px-2 py-1 text-xs">
                        {session.device_code}
                      </code>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copy(session.device_code ?? "")}
                      >
                        {copiedValue === session.device_code
                          ? "Copied!"
                          : "Copy code"}
                      </Button>
                    </div>
                  )}
                  {session.recent_output && (
                    <pre className="mt-3 max-h-40 overflow-auto rounded bg-background p-3 text-xs text-muted-foreground">
                      {session.recent_output}
                    </pre>
                  )}
                  {provider.provider === "claude_code" &&
                    !isTerminalSessionState(session.state) && (
                      <div className="mt-3 space-y-2">
                        <p className="text-xs text-muted-foreground">
                          If Claude finishes sign-in by showing a one-time code,
                          paste it here to send it back to the worker CLI.
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <Input
                            value={sessionInputs[provider.provider] ?? ""}
                            onChange={(event) => {
                              const value = event.target.value;
                              setSessionInputs((current) => ({
                                ...current,
                                [provider.provider]: value,
                              }));
                            }}
                            placeholder="Paste Claude auth code"
                            className="max-w-sm bg-background"
                          />
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              void handleSubmitSessionInput(
                                provider.provider,
                                session.session_id,
                              );
                            }}
                            disabled={
                              pendingInputProvider === provider.provider
                            }
                          >
                            {pendingInputProvider === provider.provider && (
                              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                            )}
                            Submit code
                          </Button>
                        </div>
                      </div>
                    )}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  onClick={() => {
                    void handleConnect(provider.provider);
                  }}
                  disabled={isBusy}
                >
                  {isBusy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {connectLabel}
                </Button>
                {provider.executable_path && (
                  <code className="rounded bg-muted px-2 py-1 text-xs">
                    {provider.executable_path}
                  </code>
                )}
              </div>
            </CardContent>
          </Card>
        );
      }),
    [
      copiedValue,
      copy,
      handleConnect,
      handleSubmitSessionInput,
      loginSessions,
      pendingProvider,
      pendingInputProvider,
      providerStatuses,
      sessionInputs,
    ],
  );

  return (
    <div className="space-y-4">
      {statusError && (
        <Alert variant="destructive">
          <AlertTitle>External agent status failed</AlertTitle>
          <AlertDescription>{statusError}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle>External Agents</CardTitle>
              <CardDescription>
                Connect Claude Code and Codex once per worker from Canvas. OAuth
                happens on the execution worker, not on individual workflow
                nodes or the local browser-aware bridge below.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void queueStatusRefresh();
              }}
              disabled={isRefreshingStatuses}
            >
              {isRefreshingStatuses ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoadingStatuses && providerStatuses.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Loading worker runtime status...
            </p>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">{providerCards}</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Local Agent Context Bridge</CardTitle>
          <CardDescription>
            Use the browser-aware CLI bridge when you want a local terminal
            agent to understand the workflow currently open in Canvas. This does
            not authenticate worker-side Claude Code or Codex workflow nodes.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <h3 className="text-sm font-medium">Quick start</h3>
            <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
              <li>
                Authenticate the local Orcheo CLI:
                <div className="mt-1 flex items-center gap-2">
                  <code className="rounded bg-muted px-2 py-1 text-xs">
                    orcheo auth login
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={() => copy("orcheo auth login")}
                  >
                    {copiedValue === "orcheo auth login" ? "Copied!" : "Copy"}
                  </Button>
                </div>
              </li>
              <li>
                Start the browser context bridge:
                <div className="mt-1 flex items-center gap-2">
                  <code className="rounded bg-muted px-2 py-1 text-xs">
                    orcheo browser-aware
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={() => copy("orcheo browser-aware")}
                  >
                    {copiedValue === "orcheo browser-aware"
                      ? "Copied!"
                      : "Copy"}
                  </Button>
                </div>
              </li>
              <li>
                Open a workflow in Canvas. Your local agent can then inspect the
                active workflow context from the terminal.
              </li>
            </ol>
          </div>

          <Separator />

          <div className="space-y-2">
            <h3 className="text-sm font-medium">Bridge status</h3>
            <div className="flex items-center gap-2">
              <Badge variant={serverRunning ? "default" : "secondary"}>
                {serverRunning ? "Bridge connected" : "Bridge offline"}
              </Badge>
              {serverRunning && sessionCount !== null && (
                <span className="text-sm text-muted-foreground">
                  {sessionCount} active{" "}
                  {sessionCount === 1 ? "session" : "sessions"}
                </span>
              )}
            </div>
            {!serverRunning && (
              <p className="text-xs text-muted-foreground">
                Run{" "}
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo browser-aware
                </code>{" "}
                in your terminal to connect.
              </p>
            )}
          </div>

          <Separator />

          <div className="space-y-2">
            <h3 className="text-sm font-medium">Agent commands</h3>
            <div className="space-y-1 text-sm text-muted-foreground">
              <p>
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo context
                </code>{" "}
                — See what workflow you have open
              </p>
              <p>
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo workflow show &lt;id&gt;
                </code>{" "}
                — View workflow details
              </p>
              <p>
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo workflow download &lt;id&gt;
                </code>{" "}
                — Download workflow script
              </p>
              <p>
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo workflow upload --id &lt;id&gt; &lt;file&gt;
                </code>{" "}
                — Upload updated script
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AgentSettingsTab;
