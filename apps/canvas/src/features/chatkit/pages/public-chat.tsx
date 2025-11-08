import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ChatKit, useChatKit } from "@openai/chatkit-react";

import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
import { Button } from "@/design-system/ui/button";
import { Skeleton } from "@/design-system/ui/skeleton";
import {
  buildBackendHttpUrl,
  getBackendBaseUrl,
  getChatKitDomainKey,
} from "@/lib/config";

import {
  createChatKitFetch,
  type PublishAuthError,
} from "../lib/chatkit-fetch";
import {
  clearPublishToken,
  getPublishToken,
  storePublishToken,
} from "../lib/publish-token-store";

interface WorkflowMetadata {
  id: string;
  name: string;
  require_login: boolean;
  is_public: boolean;
}

interface WorkflowMetadataError {
  status: number;
  message: string;
}

const DEFAULT_ERROR_MESSAGE =
  "We couldn't start a chat session for this workflow. Please contact the workflow owner if this issue persists.";

const HISTORY_TOKEN_KEY = "chatkitPublishTokens";

type HistoryState = {
  [HISTORY_TOKEN_KEY]?: Record<string, string>;
};

interface ChatKitWidgetProps {
  options: Parameters<typeof useChatKit>[0];
}

function ChatKitWidget({ options }: ChatKitWidgetProps) {
  const { control } = useChatKit(options);
  return <ChatKit control={control} className="flex h-full w-full flex-col" />;
}

const readHistoryToken = (workflowId: string): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  const state = (window.history.state ?? {}) as HistoryState;
  const tokens = state[HISTORY_TOKEN_KEY];
  if (!tokens) {
    return null;
  }
  return tokens[workflowId] ?? null;
};

const persistHistoryToken = (
  workflowId: string,
  token: string,
  search: string,
) => {
  if (typeof window === "undefined") {
    return;
  }
  const currentState = window.history.state;
  const state =
    currentState && typeof currentState === "object"
      ? (currentState as HistoryState)
      : ({} as HistoryState);
  const existing = state[HISTORY_TOKEN_KEY] ?? {};
  const nextState: HistoryState = {
    ...state,
    [HISTORY_TOKEN_KEY]: {
      ...existing,
      [workflowId]: token,
    },
  };

  const params = new URLSearchParams(search);
  params.delete("token");
  const nextSearch = params.toString();
  const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ""}`;
  window.history.replaceState(nextState, "", nextUrl);
};

const removeHistoryToken = (workflowId: string) => {
  if (typeof window === "undefined") {
    return;
  }
  const currentState = window.history.state;
  if (!currentState || typeof currentState !== "object") {
    return;
  }
  const tokens = (currentState as HistoryState)[HISTORY_TOKEN_KEY];
  if (!tokens || !tokens[workflowId]) {
    return;
  }
  const nextTokens = { ...tokens };
  delete nextTokens[workflowId];

  const baseState = { ...(currentState as HistoryState) };
  if (Object.keys(nextTokens).length > 0) {
    baseState[HISTORY_TOKEN_KEY] = nextTokens;
  } else {
    delete baseState[HISTORY_TOKEN_KEY];
  }

  window.history.replaceState(
    baseState,
    "",
    `${window.location.pathname}${window.location.search}`,
  );
};

const mapAuthErrorToMessage = (error: PublishAuthError): string => {
  switch (error.code) {
    case "chatkit.auth.oauth_required":
      return "Sign in is required to continue. Please authenticate and then try again.";
    case "chatkit.auth.invalid_publish_token":
    case "chatkit.auth.publish_token_missing":
      return "This share link is no longer valid. Contact the workflow owner to request a new link.";
    case "chatkit.auth.not_published":
      return "This workflow is no longer published. Contact the owner to confirm its status.";
    default:
      return DEFAULT_ERROR_MESSAGE;
  }
};

const mapMetadataErrorMessage = (error: WorkflowMetadataError): string => {
  if (error.status === 404) {
    return "We couldn't find this workflow. The link may be incorrect or the workflow has been removed.";
  }
  if (error.status === 410) {
    return "This workflow is no longer available. Contact the workflow owner for an updated link.";
  }
  if (error.status === 403) {
    return "You don't have access to view this workflow. Contact the workflow owner for assistance.";
  }
  return DEFAULT_ERROR_MESSAGE;
};

const PublicChatSkeleton = () => (
  <div className="flex flex-1 flex-col gap-4">
    <Skeleton className="h-7 w-56" />
    <Skeleton className="h-4 w-72" />
    <div className="flex flex-1 flex-col gap-3">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-full w-full" />
    </div>
  </div>
);

export default function PublicChatPage() {
  const { workflowId: routeWorkflowId } = useParams<{ workflowId: string }>();
  const location = useLocation();

  const workflowId = routeWorkflowId?.trim() ?? "";
  const [workflow, setWorkflow] = useState<WorkflowMetadata | null>(null);
  const [metadataError, setMetadataError] =
    useState<WorkflowMetadataError | null>(null);
  const [isMetadataLoading, setIsMetadataLoading] = useState<boolean>(true);
  const [publishToken, setPublishToken] = useState<string | null>(null);
  const [authError, setAuthError] = useState<PublishAuthError | null>(null);
  const [rateLimitMessage, setRateLimitMessage] = useState<string | null>(null);
  const [hasAcceptedLoginRequirement, setHasAcceptedLoginRequirement] =
    useState<boolean>(false);

  const backendBaseUrl = getBackendBaseUrl();
  const domainKey = getChatKitDomainKey();

  useEffect(() => {
    if (!workflowId) {
      setPublishToken(null);
      return;
    }

    const existing = getPublishToken(workflowId);
    if (existing) {
      setPublishToken(existing);
      return;
    }

    const historyToken = readHistoryToken(workflowId);
    if (historyToken) {
      storePublishToken(workflowId, historyToken);
      setPublishToken(historyToken);
      return;
    }

    if (typeof window === "undefined") {
      setPublishToken(null);
      return;
    }

    const params = new URLSearchParams(location.search);
    const tokenFromQuery = params.get("token");
    if (tokenFromQuery) {
      storePublishToken(workflowId, tokenFromQuery);
      persistHistoryToken(workflowId, tokenFromQuery, location.search);
      setPublishToken(tokenFromQuery);
      return;
    }

    setPublishToken(null);
  }, [workflowId, location.search]);

  useEffect(() => {
    let isCancelled = false;

    const loadMetadata = async () => {
      if (!workflowId) {
        setWorkflow(null);
        setMetadataError({ status: 404, message: "Workflow not found" });
        setIsMetadataLoading(false);
        return;
      }

      setIsMetadataLoading(true);
      setMetadataError(null);

      try {
        const response = await fetch(
          buildBackendHttpUrl(`/api/workflows/${workflowId}`),
          {
            credentials: "include",
          },
        );

        const text = await response.text();
        const payload = text ? (JSON.parse(text) as WorkflowMetadata) : null;

        if (!response.ok || !payload) {
          const status = response.status || 500;
          const message =
            (payload && (payload as unknown as { detail?: string }).detail) ||
            response.statusText ||
            "Failed to load workflow metadata.";
          throw { status, message } satisfies WorkflowMetadataError;
        }

        if (isCancelled) {
          return;
        }

        if (!payload.is_public) {
          setWorkflow(null);
          setMetadataError({
            status: 403,
            message: "Workflow is not published",
          });
          setIsMetadataLoading(false);
          return;
        }

        setWorkflow(payload);
        setMetadataError(null);
        setIsMetadataLoading(false);
      } catch (error) {
        if (isCancelled) {
          return;
        }
        const failure =
          error && typeof error === "object"
            ? (error as WorkflowMetadataError)
            : { status: 500, message: DEFAULT_ERROR_MESSAGE };
        setWorkflow(null);
        setMetadataError(failure);
        setIsMetadataLoading(false);
      }
    };

    void loadMetadata();

    return () => {
      isCancelled = true;
    };
  }, [workflowId]);

  useEffect(() => {
    if (workflow && !workflow.require_login) {
      setHasAcceptedLoginRequirement(true);
    }
  }, [workflow]);

  const handleAuthError = useCallback(
    (error: PublishAuthError) => {
      setAuthError(error);
      setRateLimitMessage(null);
      if (error.code === "chatkit.auth.invalid_publish_token") {
        clearPublishToken(workflowId);
        removeHistoryToken(workflowId);
        setPublishToken(null);
      }
      if (error.code === "chatkit.auth.oauth_required") {
        setHasAcceptedLoginRequirement(false);
      }
    },
    [workflowId],
  );

  const handleRateLimitChange = useCallback((message: string | null) => {
    setRateLimitMessage(message);
  }, []);

  const chatkitOptions = useMemo(() => {
    if (
      !workflowId ||
      !publishToken ||
      !workflow ||
      (workflow.require_login && !hasAcceptedLoginRequirement) ||
      authError
    ) {
      return null;
    }

    return {
      api: {
        url: `${backendBaseUrl}/api/chatkit`,
        domainKey,
        fetch: createChatKitFetch({
          workflowId,
          publishToken,
          onAuthError: handleAuthError,
          onRateLimitChange: handleRateLimitChange,
        }),
      },
      header: {
        enabled: true,
        title: { text: workflow.name },
      },
      composer: {
        placeholder: `Chat with ${workflow.name}`,
      },
    };
  }, [
    authError,
    backendBaseUrl,
    domainKey,
    handleAuthError,
    handleRateLimitChange,
    hasAcceptedLoginRequirement,
    publishToken,
    workflow,
    workflowId,
  ]);

  const handleStartChat = () => {
    setAuthError(null);
    setRateLimitMessage(null);
    setHasAcceptedLoginRequirement(true);
  };

  const missingToken = !publishToken && !isMetadataLoading;
  const shouldShowChat = Boolean(chatkitOptions);

  return (
    <div className="min-h-screen bg-muted py-10">
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4">
        <div className="rounded-lg border bg-background p-6 shadow-sm">
          <header className="mb-6 space-y-2">
            {isMetadataLoading ? (
              <Skeleton className="h-8 w-64" />
            ) : (
              <>
                <h1 className="text-2xl font-semibold tracking-tight">
                  {workflow?.name ?? "Workflow chat"}
                </h1>
                <p className="text-sm text-muted-foreground">
                  Powered by Orcheo ChatKit
                </p>
              </>
            )}
          </header>

          <div className="flex flex-col gap-4">
            {rateLimitMessage && (
              <Alert variant="destructive">
                <AlertTitle>Rate limit reached</AlertTitle>
                <AlertDescription>{rateLimitMessage}</AlertDescription>
              </Alert>
            )}

            {metadataError && !isMetadataLoading && (
              <Alert variant="destructive">
                <AlertTitle>Unable to load workflow</AlertTitle>
                <AlertDescription>
                  {mapMetadataErrorMessage(metadataError)}
                </AlertDescription>
              </Alert>
            )}

            {missingToken && !metadataError && (
              <Alert variant="destructive">
                <AlertTitle>Publish token missing</AlertTitle>
                <AlertDescription>
                  This share link is missing a publish token. Contact the
                  workflow owner to request a new link.
                </AlertDescription>
              </Alert>
            )}

            {authError && (
              <Alert variant="destructive">
                <AlertTitle>Chat unavailable</AlertTitle>
                <AlertDescription>
                  {mapAuthErrorToMessage(authError)}
                </AlertDescription>
              </Alert>
            )}

            {workflow?.require_login &&
              !hasAcceptedLoginRequirement &&
              !metadataError &&
              !isMetadataLoading &&
              !missingToken && (
                <Alert>
                  <AlertTitle>Sign in required</AlertTitle>
                  <AlertDescription className="space-y-3">
                    <p>
                      This workflow requires an OAuth login before you can start
                      chatting. Sign in with your Orcheo account, then return to
                      this page and start the chat.
                    </p>
                    <div className="flex flex-wrap gap-3">
                      <Button asChild>
                        <Link to="/login">Sign in</Link>
                      </Button>
                      <Button variant="outline" onClick={handleStartChat}>
                        Start chat
                      </Button>
                    </div>
                  </AlertDescription>
                </Alert>
              )}

            <div className="flex min-h-[540px] flex-1">
              {isMetadataLoading ? (
                <PublicChatSkeleton />
              ) : shouldShowChat ? (
                <div className="flex h-[520px] w-full flex-col overflow-hidden rounded-lg border bg-background">
                  <ChatKitWidget options={chatkitOptions} />
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm text-muted-foreground">
                  <p className="max-w-prose">
                    {metadataError || missingToken
                      ? "Provide a valid publish link to start chatting with this workflow."
                      : "Complete the required steps above to launch the chat experience."}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
