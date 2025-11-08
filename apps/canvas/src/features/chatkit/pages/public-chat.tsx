import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Skeleton } from "@/design-system/ui/skeleton";
import { getBackendBaseUrl, buildBackendHttpUrl } from "@/lib/config";

import { PublishChatPanel } from "../components/publish-chat-panel";
import {
  ensurePublishToken,
  getPublishToken,
  setPublishToken,
} from "../utils/publish-token-store";

const CONTACT_OWNER_MESSAGE =
  "If you believe you should have access, please contact the workflow owner.";

const hasOAuthSession = () => {
  if (typeof document === "undefined") {
    return false;
  }
  return /(?:^|;\s*)orcheo_oauth_session=/.test(document.cookie);
};

type WorkflowMetadata = {
  id: string;
  name: string;
  is_public: boolean;
  require_login: boolean;
};

type MetadataState =
  | { status: "loading" }
  | { status: "error"; code: string; message: string }
  | { status: "ready"; workflow: WorkflowMetadata };

type ChatErrorState = { type: "none" | "auth" | "rate_limit" };

const friendlyErrorMessage = (state: MetadataState) => {
  if (state.status !== "error") {
    return null;
  }

  switch (state.code) {
    case "not_found":
      return "We couldn't find a workflow matching this link.";
    case "unpublished":
      return "This workflow is no longer published.";
    case "unauthorized":
      return "You need to sign in before accessing this workflow.";
    default:
      return "Something went wrong while loading this workflow.";
  }
};

const buildLoginUrl = (pathname: string) =>
  `/login?redirect=${encodeURIComponent(pathname)}`;

export default function PublicChatPage() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const [metadata, setMetadata] = useState<MetadataState>({
    status: "loading",
  });
  const [chatError, setChatError] = useState<ChatErrorState>({ type: "none" });
  const [rateLimitMessageVisible, setRateLimitMessageVisible] = useState(false);

  const backendBaseUrl = getBackendBaseUrl();

  useEffect(() => {
    ensurePublishToken();
  }, []);

  useEffect(() => {
    if (!workflowId) {
      setMetadata({
        status: "error",
        code: "not_found",
        message: "A workflow identifier is required.",
      });
      return;
    }

    let isMounted = true;
    const controller = new AbortController();

    const loadMetadata = async () => {
      setChatError({ type: "none" });
      setMetadata({ status: "loading" });
      try {
        const response = await fetch(
          buildBackendHttpUrl(`/api/workflows/${workflowId}`, backendBaseUrl),
          { credentials: "include", signal: controller.signal },
        );

        if (!isMounted) {
          return;
        }

        if (response.status === 404) {
          setMetadata({
            status: "error",
            code: "not_found",
            message: "Workflow not found",
          });
          return;
        }

        if (response.status === 403) {
          setMetadata({
            status: "error",
            code: "unpublished",
            message: "Workflow is not published",
          });
          return;
        }

        if (response.status === 401) {
          setMetadata({
            status: "error",
            code: "unauthorized",
            message: "Authentication required",
          });
          return;
        }

        if (!response.ok) {
          setMetadata({
            status: "error",
            code: "unknown",
            message: "Failed to load workflow metadata",
          });
          return;
        }

        const data = (await response.json()) as WorkflowMetadata;
        if (!data.is_public) {
          setMetadata({
            status: "error",
            code: "unpublished",
            message: "Workflow is not published",
          });
          return;
        }

        setMetadata({ status: "ready", workflow: data });
      } catch (error) {
        if (!isMounted) {
          return;
        }
        if ((error as Error).name === "AbortError") {
          return;
        }
        setMetadata({
          status: "error",
          code: "unknown",
          message: (error as Error).message,
        });
      }
    };

    loadMetadata();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [backendBaseUrl, workflowId]);

  useEffect(() => {
    if (chatError.type === "rate_limit") {
      setRateLimitMessageVisible(true);
      const timeout = window.setTimeout(() => {
        setRateLimitMessageVisible(false);
      }, 5000);
      return () => window.clearTimeout(timeout);
    }
    return undefined;
  }, [chatError.type]);

  const publishToken = getPublishToken();

  const handleAuthError = useCallback(() => {
    setChatError({ type: "auth" });
  }, []);

  const handleRateLimit = useCallback(() => {
    setChatError({ type: "rate_limit" });
  }, []);

  const contactCta = useMemo(() => CONTACT_OWNER_MESSAGE, []);

  const requiresLogin = useMemo(() => {
    if (metadata.status !== "ready") {
      return false;
    }
    return metadata.workflow.require_login && !hasOAuthSession();
  }, [metadata]);

  const handleTokenReset = () => {
    setPublishToken(null);
    navigate(0);
  };

  const renderContent = () => {
    if (!workflowId) {
      return (
        <ErrorCard
          title="Missing workflow"
          description="The chat URL is missing a workflow identifier."
          contactMessage={contactCta}
        />
      );
    }

    if (!publishToken) {
      return (
        <ErrorCard
          title="Publish token required"
          description="This chat link needs a publish token to authenticate."
          contactMessage={contactCta}
          primaryAction={{ label: "Reload", onClick: () => navigate(0) }}
        />
      );
    }

    if (metadata.status === "loading") {
      return <LoadingSkeleton />;
    }

    if (metadata.status === "error") {
      return (
        <ErrorCard
          title="Unable to load workflow"
          description={friendlyErrorMessage(metadata) ?? metadata.message}
          contactMessage={contactCta}
          primaryAction={{ label: "Retry", onClick: () => navigate(0) }}
        />
      );
    }

    if (requiresLogin) {
      return (
        <LoginRequiredCard
          workflowName={metadata.workflow.name}
          loginUrl={buildLoginUrl(location.pathname)}
        />
      );
    }

    if (chatError.type === "auth") {
      return (
        <ErrorCard
          title="Authentication needed"
          description="The publish token no longer works for this workflow."
          contactMessage={contactCta}
          primaryAction={{
            label: "Try another token",
            onClick: handleTokenReset,
          }}
        />
      );
    }

    return (
      <div className="flex h-full w-full flex-col gap-4">
        <Card className="border-muted">
          <CardHeader className="pb-3">
            <CardTitle className="text-xl font-semibold">
              {metadata.workflow.name}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0 text-sm text-muted-foreground">
            Chat with this published workflow. Your conversation may be recorded
            for quality review.
          </CardContent>
        </Card>

        {rateLimitMessageVisible && chatError.type === "rate_limit" && (
          <Alert variant="default">
            <AlertTitle>Slow down</AlertTitle>
            <AlertDescription>
              You have hit a temporary rate limit. Please wait a few moments
              before sending another message.
            </AlertDescription>
          </Alert>
        )}

        <div className="flex-1 overflow-hidden rounded-lg border bg-background">
          {metadata.status === "ready" && publishToken ? (
            <PublishChatPanel
              workflowId={metadata.workflow.id}
              workflowName={metadata.workflow.name}
              publishToken={publishToken}
              onAuthError={handleAuthError}
              onRateLimit={handleRateLimit}
            />
          ) : (
            <LoadingSkeleton />
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b bg-card/60 backdrop-blur">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-semibold text-primary">
            Orcheo Chat
          </Link>
          <span className="text-sm text-muted-foreground">
            Powered by Orcheo workflows
          </span>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-4xl flex-1 items-stretch justify-center px-4 py-8">
        <div className="flex w-full flex-col">{renderContent()}</div>
      </main>
    </div>
  );
}

type ErrorCardProps = {
  title: string;
  description: string;
  contactMessage?: string;
  primaryAction?: { label: string; onClick: () => void };
};

const ErrorCard = ({
  title,
  description,
  contactMessage,
  primaryAction,
}: ErrorCardProps) => (
  <Card className="mx-auto w-full max-w-xl border-destructive/40">
    <CardHeader>
      <CardTitle>{title}</CardTitle>
    </CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm text-muted-foreground">{description}</p>
      {contactMessage ? (
        <p className="text-xs text-muted-foreground/80">{contactMessage}</p>
      ) : null}
      {primaryAction ? (
        <Button onClick={primaryAction.onClick}>{primaryAction.label}</Button>
      ) : null}
    </CardContent>
  </Card>
);

type LoginRequiredCardProps = {
  workflowName: string;
  loginUrl: string;
};

const LoginRequiredCard = ({
  workflowName,
  loginUrl,
}: LoginRequiredCardProps) => (
  <Card className="mx-auto w-full max-w-xl border-primary/40">
    <CardHeader>
      <CardTitle>Login required</CardTitle>
    </CardHeader>
    <CardContent className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {workflowName} requires you to sign in before chatting.
      </p>
      <Button asChild>
        <Link to={loginUrl}>Sign in to continue</Link>
      </Button>
      <p className="text-xs text-muted-foreground/80">
        {CONTACT_OWNER_MESSAGE}
      </p>
    </CardContent>
  </Card>
);

const LoadingSkeleton = () => (
  <div className="flex h-full flex-col gap-4">
    <Skeleton className="h-24 w-full" />
    <Skeleton className="h-full w-full" />
  </div>
);
