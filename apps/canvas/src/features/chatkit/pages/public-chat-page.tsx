import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Skeleton } from "@/design-system/ui/skeleton";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { AlertCircle, Lock, RefreshCw, ShieldAlert } from "lucide-react";

import {
  buildBackendHttpUrl,
  getBackendBaseUrl,
  getChatkitDomainKey,
} from "@/lib/config";
import {
  readPublishToken,
  rememberPublishToken,
} from "@features/chatkit/lib/publish-token-store";

interface ChatKitWorkflowMetadata {
  id: string;
  name: string;
  is_public: boolean;
  require_login: boolean;
}

type LocationState = { publishToken?: string } | undefined;

type PageStatus = "idle" | "loading" | "ready" | "error";

type ResolvedError = {
  title: string;
  description: string;
};

const PUBLISH_TOKEN_QUERY_KEY = "token";
const PUBLISH_TOKEN_HEADER = "X-Orcheo-Publish-Token";

const checkOAuthSession = (): boolean => {
  if (typeof document === "undefined") {
    return false;
  }
  return document.cookie
    .split(";")
    .map((entry) => entry.trim())
    .some((entry) => entry.startsWith("orcheo_oauth_session="));
};

const describeMetadataFailure = (
  statusCode: number,
  detail: unknown,
): ResolvedError => {
  if (statusCode === 401) {
    return {
      title: "Access token invalid or expired",
      description:
        "This share link no longer has a valid publish token. Ask the workflow owner to rotate the token and send you a new link.",
    };
  }

  if (statusCode === 403) {
    return {
      title: "Workflow is no longer public",
      description:
        "The workflow owner has revoked public access. Reach out to them if you believe this is a mistake.",
    };
  }

  if (statusCode === 429) {
    return {
      title: "Too many requests",
      description:
        "We have temporarily rate limited requests for this workflow. Please wait a moment before trying again.",
    };
  }

  const detailMessage =
    typeof detail === "string"
      ? detail
      : typeof detail === "object" && detail !== null
        ? (detail as { message?: string }).message
        : undefined;

  return {
    title: "Unable to load workflow",
    description:
      detailMessage ||
      "An unexpected error occurred while loading this workflow. Try refreshing the page or contact the workflow owner.",
  };
};

const describeChatFailure = (
  statusCode: number,
  detail: unknown,
): ResolvedError => {
  if (statusCode === 429) {
    return {
      title: "Rate limit exceeded",
      description:
        "We are receiving too many requests right now. Wait a few seconds before sending another message.",
    };
  }

  if (statusCode === 401 || statusCode === 403) {
    return {
      title: "Access denied",
      description:
        "Your publish token or session is no longer valid. Refresh the page or ask the workflow owner for a new link.",
    };
  }

  const detailMessage =
    typeof detail === "string"
      ? detail
      : typeof detail === "object" && detail !== null
        ? (detail as { message?: string }).message
        : undefined;

  return {
    title: "Chat unavailable",
    description:
      detailMessage ??
      "Something went wrong while contacting the workflow. Try again shortly or let the workflow owner know about the issue.",
  };
};

export default function PublicChatPage(): JSX.Element {
  const { workflowId } = useParams<{ workflowId: string }>();
  const location = useLocation<LocationState>();
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState<PageStatus>("idle");
  const [metadata, setMetadata] = useState<ChatKitWorkflowMetadata | null>(
    null,
  );
  const [error, setError] = useState<ResolvedError | null>(null);
  const [chatError, setChatError] = useState<ResolvedError | null>(null);
  const [rateLimitNotice, setRateLimitNotice] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [hasSession, setHasSession] = useState<boolean>(checkOAuthSession());
  const [isRefreshingSession, setIsRefreshingSession] = useState(false);
  const isMountedRef = useRef(true);

  const backendBaseUrl = useMemo(() => getBackendBaseUrl(), []);
  const chatkitDomainKey = useMemo(() => getChatkitDomainKey(), []);

  useEffect(
    () => () => {
      isMountedRef.current = false;
    },
    [],
  );

  useEffect(() => {
    if (!workflowId) {
      setToken(null);
      return;
    }

    let resolvedToken: string | undefined;
    const stateToken = location.state?.publishToken;
    if (stateToken) {
      resolvedToken = stateToken;
      rememberPublishToken(workflowId, stateToken);
    }

    if (!resolvedToken) {
      resolvedToken = readPublishToken(workflowId) ?? undefined;
    }

    if (!resolvedToken) {
      const queryToken = searchParams.get(PUBLISH_TOKEN_QUERY_KEY);
      if (queryToken) {
        resolvedToken = queryToken;
        rememberPublishToken(workflowId, queryToken);
        const nextParams = new URLSearchParams(searchParams);
        nextParams.delete(PUBLISH_TOKEN_QUERY_KEY);
        setSearchParams(nextParams, { replace: true });
      }
    }

    setToken((previous) =>
      previous === resolvedToken ? previous : (resolvedToken ?? null),
    );
  }, [location.state, searchParams, setSearchParams, workflowId]);

  useEffect(() => {
    if (!workflowId || !token) {
      return;
    }

    let cancelled = false;
    const abortController = new AbortController();

    const loadMetadata = async () => {
      setStatus("loading");
      setError(null);
      setChatError(null);
      setRateLimitNotice(null);

      try {
        const response = await fetch(
          buildBackendHttpUrl(
            `/api/chatkit/workflows/${workflowId}`,
            backendBaseUrl,
          ),
          {
            method: "GET",
            headers: {
              [PUBLISH_TOKEN_HEADER]: token,
              Accept: "application/json",
            },
            signal: abortController.signal,
          },
        );

        if (!response.ok) {
          const detail = await response
            .clone()
            .json()
            .catch(async () =>
              response
                .clone()
                .text()
                .catch(() => undefined),
            );
          if (!cancelled && isMountedRef.current) {
            setStatus("error");
            setError(describeMetadataFailure(response.status, detail));
            setMetadata(null);
          }
          return;
        }

        const payload = (await response.json()) as ChatKitWorkflowMetadata;
        if (!cancelled && isMountedRef.current) {
          setMetadata(payload);
          setStatus("ready");
          setHasSession(payload.require_login ? checkOAuthSession() : true);
        }
      } catch (caught) {
        if (cancelled || !isMountedRef.current) {
          return;
        }
        if ((caught as Error).name === "AbortError") {
          return;
        }
        setStatus("error");
        setError({
          title: "Unable to load workflow",
          description:
            (caught as Error).message ||
            "An unexpected error occurred while loading this workflow.",
        });
        setMetadata(null);
      }
    };

    void loadMetadata();

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [backendBaseUrl, token, workflowId]);

  const clearChatIssues = useCallback(() => {
    if (!isMountedRef.current) {
      return;
    }
    setChatError(null);
    setRateLimitNotice(null);
  }, []);

  const publishAwareFetch = useMemo(() => {
    if (!workflowId || !token) {
      return undefined;
    }

    const baseFetch =
      typeof globalThis.fetch === "function"
        ? globalThis.fetch.bind(globalThis)
        : undefined;

    return async (
      input: Parameters<typeof fetch>[0],
      init?: Parameters<typeof fetch>[1],
    ) => {
      clearChatIssues();

      const nextInit: RequestInit = { ...(init ?? {}) };
      const headers = new Headers(nextInit.headers ?? {});
      headers.set(PUBLISH_TOKEN_HEADER, token);
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }

      if (typeof nextInit.body === "string") {
        try {
          const payload = JSON.parse(nextInit.body);
          if (payload && typeof payload === "object") {
            if (!payload.workflow_id) {
              payload.workflow_id = workflowId;
            }
            if (!payload.workflowId) {
              payload.workflowId = workflowId;
            }
            payload.publish_token = token;
            payload.publishToken = token;
            nextInit.body = JSON.stringify(payload);
          }
        } catch {
          // ignore malformed JSON payloads
        }
      }

      nextInit.headers = headers;

      const response = await (baseFetch ?? fetch)(input, nextInit);

      if (!isMountedRef.current) {
        return response;
      }

      if (response.status >= 400) {
        const detail = await response
          .clone()
          .json()
          .catch(async () =>
            response
              .clone()
              .text()
              .catch(() => undefined),
          );

        const resolved = describeChatFailure(response.status, detail);
        if (response.status === 429) {
          setRateLimitNotice(resolved.description);
        } else {
          setChatError(resolved);
          setRateLimitNotice(null);
        }
      } else {
        clearChatIssues();
      }

      return response;
    };
  }, [clearChatIssues, token, workflowId]);

  const chatKitOptions = useMemo(() => {
    const apiConfig = {
      url: buildBackendHttpUrl("/api/chatkit", backendBaseUrl),
      domainKey: chatkitDomainKey,
      fetch: publishAwareFetch ?? fetch,
    } as const;

    return {
      api: apiConfig,
      header: {
        enabled: true,
        title: { text: metadata?.name ?? "Workflow Chat" },
      },
      composer: {
        placeholder: metadata
          ? `Ask ${metadata.name} a question…`
          : "Preparing workflow chat…",
      },
      onResponseStart: clearChatIssues,
    };
  }, [
    backendBaseUrl,
    chatkitDomainKey,
    clearChatIssues,
    metadata,
    publishAwareFetch,
  ]);

  const { control } = useChatKit(chatKitOptions);

  const handleLoginRedirect = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }
    const redirectTarget = window.location.href;
    const loginUrl = `/login?redirect=${encodeURIComponent(redirectTarget)}`;
    window.location.assign(loginUrl);
  }, []);

  const handleRefreshSession = useCallback(() => {
    setIsRefreshingSession(true);
    setTimeout(() => {
      if (!isMountedRef.current) {
        return;
      }
      setHasSession(checkOAuthSession());
      setIsRefreshingSession(false);
    }, 350);
  }, []);

  const showLoginPrompt =
    status === "ready" && metadata?.require_login && !hasSession;

  let mainContent: JSX.Element;

  if (!token) {
    mainContent = (
      <Alert variant="destructive">
        <AlertCircle className="h-5 w-5" />
        <AlertTitle>Missing access token</AlertTitle>
        <AlertDescription>
          This chat link did not include a publish token. Ask the workflow owner
          to resend the link or generate a new token.
        </AlertDescription>
      </Alert>
    );
  } else if (status === "loading") {
    mainContent = (
      <Card className="border-dashed">
        <CardHeader>
          <CardTitle>
            <Skeleton className="h-6 w-40" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-[420px] w-full" />
        </CardContent>
      </Card>
    );
  } else if (status === "error" && error) {
    mainContent = (
      <Alert variant="destructive">
        <AlertCircle className="h-5 w-5" />
        <AlertTitle>{error.title}</AlertTitle>
        <AlertDescription>{error.description}</AlertDescription>
      </Alert>
    );
  } else if (metadata) {
    mainContent = (
      <div className="space-y-4">
        {showLoginPrompt && (
          <Alert>
            <Lock className="h-5 w-5" />
            <AlertTitle>Login required</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>
                This workflow requires an authenticated session. Sign in using
                the button below, then refresh your access.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button onClick={handleLoginRedirect}>Sign in</Button>
                <Button
                  variant="outline"
                  onClick={handleRefreshSession}
                  disabled={isRefreshingSession}
                  className="inline-flex items-center gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  {isRefreshingSession ? "Checking…" : "Refresh access"}
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {rateLimitNotice && (
          <Alert>
            <ShieldAlert className="h-5 w-5" />
            <AlertTitle>Rate limited</AlertTitle>
            <AlertDescription>{rateLimitNotice}</AlertDescription>
          </Alert>
        )}

        {chatError && (
          <Alert variant="destructive">
            <AlertCircle className="h-5 w-5" />
            <AlertTitle>{chatError.title}</AlertTitle>
            <AlertDescription>{chatError.description}</AlertDescription>
          </Alert>
        )}

        {!showLoginPrompt && (
          <Card>
            <CardHeader>
              <CardTitle>{metadata.name}</CardTitle>
            </CardHeader>
            <CardContent className="h-[600px]">
              <ChatKit control={control} className="flex h-full flex-col" />
            </CardContent>
          </Card>
        )}
      </div>
    );
  } else {
    mainContent = (
      <Alert>
        <AlertCircle className="h-5 w-5" />
        <AlertTitle>Preparing chat</AlertTitle>
        <AlertDescription>
          We&apos;re getting everything ready. This should only take a moment.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
            Orcheo Workflow Chat
          </p>
          {metadata && status === "ready" ? (
            <h1 className="text-3xl font-semibold">{metadata.name}</h1>
          ) : status === "loading" ? (
            <Skeleton className="h-9 w-64" />
          ) : (
            <h1 className="text-3xl font-semibold">Workflow Chat</h1>
          )}
          {metadata && status === "ready" && (
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant={metadata.require_login ? "secondary" : "outline"}>
                {metadata.require_login ? "Login required" : "Public access"}
              </Badge>
            </div>
          )}
        </div>

        {mainContent}
      </div>
    </div>
  );
}
