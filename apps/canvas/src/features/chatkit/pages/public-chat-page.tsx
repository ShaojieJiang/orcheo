import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
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
import {
  buildBackendHttpUrl,
  getBackendBaseUrl,
  getChatKitDomainKey,
} from "@/lib/config";
import { ChatKit, useChatKit } from "@openai/chatkit-react";

import {
  fetchPublicWorkflow,
  PublicWorkflowError,
  type PublicWorkflowMetadata,
} from "@features/chatkit/api/public-workflow";
import {
  clearPublishToken,
  getPublishToken,
  setPublishToken,
} from "@features/chatkit/lib/publish-token-store";

import type { UseChatKitOptions } from "@openai/chatkit-react";

interface ChatKitErrorDetail {
  message: string;
  code?: string;
}

interface PublishFetchCallbacks {
  onInvalidToken: (message: string) => void;
  onOAuthRequired: (message: string) => void;
  onGenericAuthError: (message: string) => void;
  onAuthCleared: () => void;
  onRateLimit: () => void;
  onRateLimitCleared: () => void;
}

interface PublishFetchConfig extends PublishFetchCallbacks {
  workflowId: string;
  workflowName: string;
  publishToken: string;
}

const parseChatKitErrorDetail = async (
  response: Response,
): Promise<ChatKitErrorDetail> => {
  try {
    const clone = response.clone();
    const contentType = clone.headers.get("Content-Type") ?? "";
    if (!contentType.includes("application/json")) {
      return { message: response.statusText || "Request failed" };
    }
    const payload = (await clone.json()) as {
      detail?: string | { message?: string; code?: string };
      message?: string;
      code?: string;
    };
    if (!payload) {
      return { message: response.statusText || "Request failed" };
    }
    if (typeof payload.detail === "string") {
      return { message: payload.detail };
    }
    if (payload.detail && typeof payload.detail === "object") {
      return {
        message:
          payload.detail.message ?? (response.statusText || "Request failed"),
        code: payload.detail.code,
      };
    }
    return {
      message: payload.message ?? (response.statusText || "Request failed"),
      code: payload.code,
    };
  } catch {
    return { message: response.statusText || "Request failed" };
  }
};

const createChatKitFetch =
  ({
    workflowId,
    workflowName,
    publishToken,
    onInvalidToken,
    onOAuthRequired,
    onGenericAuthError,
    onAuthCleared,
    onRateLimit,
    onRateLimitCleared,
  }: PublishFetchConfig) =>
  async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const nextInit: RequestInit = {
      ...init,
      credentials: "include",
    };
    const headers = new Headers(nextInit.headers ?? {});
    nextInit.headers = headers;

    const contentType = headers.get("Content-Type");
    if (
      typeof nextInit.body === "string" &&
      contentType?.includes("application/json")
    ) {
      try {
        const payload = JSON.parse(nextInit.body) as Record<string, unknown>;
        payload.workflow_id = payload.workflow_id ?? workflowId;
        payload.publish_token = publishToken;
        payload.metadata = {
          ...(typeof payload.metadata === "object" && payload.metadata !== null
            ? (payload.metadata as Record<string, unknown>)
            : {}),
          workflow_id: workflowId,
          workflow_name: workflowName,
        };
        nextInit.body = JSON.stringify(payload);
      } catch {
        // If payload parsing fails, send the original request body.
      }
    }

    const response = await fetch(input, nextInit);

    if (response.status === 429) {
      onRateLimit();
    } else {
      onRateLimitCleared();
    }

    if (!response.ok) {
      const detail = await parseChatKitErrorDetail(response);
      switch (detail.code) {
        case "chatkit.auth.invalid_publish_token": {
          onInvalidToken(
            detail.message ||
              "The publish token is invalid or has expired. Ask the owner for a new link.",
          );
          break;
        }
        case "chatkit.auth.oauth_required": {
          onOAuthRequired(
            detail.message ||
              "Login is required before you can continue chatting with this workflow.",
          );
          break;
        }
        default: {
          onGenericAuthError(
            detail.message ||
              "Unable to authenticate with the ChatKit backend.",
          );
        }
      }
      return response;
    }

    onAuthCleared();
    return response;
  };

interface AuthErrorState {
  type: "oauth_required" | "generic";
  message: string;
}

function PublishChatWidget({ options }: { options: UseChatKitOptions }) {
  const { control } = useChatKit(options);
  return (
    <div className="flex h-[520px] w-full flex-col overflow-hidden rounded-lg border bg-background">
      <ChatKit control={control} className="flex h-full w-full flex-col" />
    </div>
  );
}

export default function PublicChatPage() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const backendBaseUrl = useMemo(() => getBackendBaseUrl(), []);
  const chatKitDomainKey = useMemo(() => getChatKitDomainKey(), []);
  const queryToken = useMemo(() => {
    const raw = searchParams.get("token");
    const trimmed = raw?.trim();
    return trimmed ? trimmed : null;
  }, [searchParams]);

  const [metadata, setMetadata] = useState<PublicWorkflowMetadata | null>(null);
  const [metadataError, setMetadataError] =
    useState<PublicWorkflowError | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [token, setToken] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [authError, setAuthError] = useState<AuthErrorState | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [isLoginConfirmed, setIsLoginConfirmed] = useState(false);

  useEffect(() => {
    if (!workflowId) {
      setToken(null);
      setTokenInput("");
      setTokenError(null);
      return;
    }

    const stored = getPublishToken(workflowId);
    if (stored) {
      setToken(stored);
      setTokenInput(stored);
      setTokenError(null);
      return;
    }

    if (queryToken) {
      setPublishToken(workflowId, queryToken);
      setToken(queryToken);
      setTokenInput(queryToken);
      setTokenError(null);
      return;
    }

    setToken(null);
    setTokenInput("");
    setTokenError(null);
  }, [queryToken, workflowId]);

  useEffect(() => {
    if (!workflowId || !queryToken) {
      return;
    }
    const nextParams = new URLSearchParams(searchParams);
    if (!nextParams.has("token")) {
      return;
    }
    nextParams.delete("token");
    setSearchParams(nextParams, { replace: true });
  }, [queryToken, searchParams, setSearchParams, workflowId]);

  useEffect(() => {
    if (!workflowId) {
      setMetadata(null);
      setMetadataError(
        new PublicWorkflowError("Workflow identifier is required.", 400),
      );
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setMetadata(null);
    setMetadataError(null);

    fetchPublicWorkflow(workflowId, { signal: controller.signal })
      .then((data) => {
        setMetadata(data);
        setIsLoginConfirmed(!data.require_login);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (error instanceof PublicWorkflowError) {
          setMetadataError(error);
        } else {
          setMetadataError(
            new PublicWorkflowError(
              "Unable to load workflow metadata. Please try again shortly.",
              500,
            ),
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [workflowId]);

  const handleTokenSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!workflowId) {
        return;
      }
      const trimmed = tokenInput.trim();
      if (!trimmed) {
        setToken(null);
        clearPublishToken(workflowId);
        setTokenError(
          "Enter the publish token provided by the workflow owner.",
        );
        return;
      }
      setPublishToken(workflowId, trimmed);
      setToken(trimmed);
      setTokenError(null);
      setRateLimited(false);
      setAuthError(null);
      setChatError(null);
    },
    [tokenInput, workflowId],
  );

  const handleTokenReset = useCallback(() => {
    if (!workflowId) {
      return;
    }
    setToken(null);
    setTokenInput("");
    clearPublishToken(workflowId);
    setTokenError(null);
    setAuthError(null);
    setChatError(null);
    setRateLimited(false);
  }, [workflowId]);

  const chatkitOptions = useMemo<UseChatKitOptions | null>(() => {
    if (!metadata || !token || (!isLoginConfirmed && metadata.require_login)) {
      return null;
    }

    return {
      api: {
        url: buildBackendHttpUrl("/api/chatkit", backendBaseUrl),
        domainKey: chatKitDomainKey,
        fetch: createChatKitFetch({
          workflowId: metadata.id,
          workflowName: metadata.name,
          publishToken: token,
          onInvalidToken: (message) => {
            setTokenError(message);
            setToken(null);
            clearPublishToken(metadata.id);
          },
          onOAuthRequired: (message) => {
            setAuthError({ type: "oauth_required", message });
          },
          onGenericAuthError: (message) => {
            setAuthError({ type: "generic", message });
          },
          onAuthCleared: () => {
            setAuthError(null);
            setTokenError(null);
            setChatError(null);
          },
          onRateLimit: () => {
            setRateLimited(true);
          },
          onRateLimitCleared: () => {
            setRateLimited(false);
          },
        }),
      },
      header: {
        enabled: true,
        title: { text: metadata.name },
      },
      history: { enabled: false },
      composer: {
        placeholder: `Chat with ${metadata.name}…`,
      },
      onError: (event) => {
        const message =
          event.detail?.error?.message ?? "An unexpected error occurred.";
        setChatError(message);
      },
      onLog: (event) => {
        if (event.detail?.name === "chatkit.rate_limited") {
          setRateLimited(true);
        }
      },
    };
  }, [backendBaseUrl, chatKitDomainKey, isLoginConfirmed, metadata, token]);

  if (workflowId === undefined) {
    return <Navigate to="/" replace />;
  }

  const loginHref = `/login?redirect=${encodeURIComponent(`/chat/${workflowId}`)}`;

  return (
    <div className="flex min-h-screen flex-col bg-muted/30">
      <header className="px-4 py-10 text-center">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Shared workflow chat
        </h1>
        <p className="mt-2 text-base text-muted-foreground">
          Start a conversation with the published workflow below using the share
          token provided by the owner.
        </p>
      </header>

      <main className="flex-1 px-4 pb-10">
        <div className="mx-auto w-full max-w-4xl">
          <Card>
            <CardHeader>
              <CardTitle>{metadata?.name ?? "Loading workflow…"}</CardTitle>
              <CardDescription>
                Workflow ID:{" "}
                <span className="font-mono text-xs sm:text-sm">
                  {workflowId}
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {isLoading && (
                <div className="space-y-4" aria-live="polite">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-[320px] w-full" />
                </div>
              )}

              {!isLoading && metadataError && (
                <Alert variant="destructive">
                  <AlertTitle>Unable to load workflow</AlertTitle>
                  <AlertDescription>
                    {metadataError.status === 404
                      ? "This workflow is not published or the identifier is incorrect. Ask the owner to confirm the share link."
                      : metadataError.message}
                  </AlertDescription>
                </Alert>
              )}

              {!isLoading && metadata && (
                <div className="space-y-6">
                  {metadata.require_login && !isLoginConfirmed && (
                    <Alert>
                      <AlertTitle>Login required</AlertTitle>
                      <AlertDescription className="space-y-3">
                        <p>
                          The owner requires visitors to authenticate before
                          chatting with this workflow. Log in and then continue.
                        </p>
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                          <Button asChild variant="secondary">
                            <Link to={loginHref}>Log in</Link>
                          </Button>
                          <Button
                            onClick={() => {
                              setIsLoginConfirmed(true);
                              setAuthError(null);
                            }}
                          >
                            I&apos;m logged in
                          </Button>
                        </div>
                      </AlertDescription>
                    </Alert>
                  )}

                  {rateLimited && (
                    <Alert variant="destructive">
                      <AlertTitle>Rate limit reached</AlertTitle>
                      <AlertDescription>
                        You have reached the request limit for this workflow.
                        Please wait a few seconds before trying again.
                      </AlertDescription>
                    </Alert>
                  )}

                  {authError && (
                    <Alert variant="destructive">
                      <AlertTitle>Authentication required</AlertTitle>
                      <AlertDescription>{authError.message}</AlertDescription>
                    </Alert>
                  )}

                  {tokenError && (
                    <Alert variant="destructive">
                      <AlertTitle>Publish token issue</AlertTitle>
                      <AlertDescription>
                        {tokenError}
                        <br />
                        Contact the workflow owner to request a fresh publish
                        token if needed.
                      </AlertDescription>
                    </Alert>
                  )}

                  <form
                    className="space-y-3"
                    onSubmit={handleTokenSubmit}
                    aria-label="Submit publish token"
                  >
                    <div className="space-y-2">
                      <Label htmlFor="publish-token">Publish token</Label>
                      <Input
                        id="publish-token"
                        value={tokenInput}
                        onChange={(event) => setTokenInput(event.target.value)}
                        placeholder="Paste the publish token you received"
                        autoComplete="off"
                        autoCorrect="off"
                        spellCheck={false}
                      />
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                      <Button type="submit">Connect to workflow</Button>
                      {token && (
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={handleTokenReset}
                        >
                          Clear token
                        </Button>
                      )}
                    </div>
                  </form>

                  {chatError && (
                    <Alert variant="destructive">
                      <AlertTitle>Chat error</AlertTitle>
                      <AlertDescription>{chatError}</AlertDescription>
                    </Alert>
                  )}

                  {token &&
                    (!metadata.require_login || isLoginConfirmed) &&
                    !tokenError &&
                    chatkitOptions && (
                      <div className="space-y-3">
                        <PublishChatWidget options={chatkitOptions} />
                      </div>
                    )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
